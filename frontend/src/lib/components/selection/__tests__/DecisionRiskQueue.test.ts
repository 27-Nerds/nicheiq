import { cleanup, fireEvent, render, waitFor } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import DecisionRiskQueue from "../DecisionRiskQueue.svelte";
import type { SolutionPreview } from "$lib/types/job";
import type {
  SelectionChallenge,
  SelectionChallengeConsensus,
  SelectionChallengeLens,
} from "$lib/types/selectionChallenge";

const apiMocks = vi.hoisted(() => ({
  getSelectionChallenges: vi.fn(),
}));

vi.mock("$lib/api", () => apiMocks);

function idea(id: string, title: string, revision = 1): SolutionPreview {
  return {
    idea_id: id,
    idea_revision: revision,
    solution_name: title,
    description: `${title} description`,
    value_proposition: `${title} value`,
  };
}

function challengeFor(
  candidate: SolutionPreview,
  lens: SelectionChallengeLens,
  consensus: SelectionChallengeConsensus,
  questionId: string,
): SelectionChallenge {
  return {
    id: `${candidate.idea_id}-${lens}-${consensus}`,
    version: 1,
    inputFingerprint: "f".repeat(64),
    ideaId: candidate.idea_id!,
    ideaRevision: candidate.idea_revision!,
    ideaTitle: candidate.solution_name,
    lens,
    overall: consensus === "contradicted" ? "contradicted" : "insufficient_evidence",
    ideaSnapshot: { solution_name: candidate.solution_name },
    subjectSnapshot: [{ key: "I1", field: "value_proposition", value: candidate.value_proposition }],
    evidenceSnapshot: [{
      key: "S1",
      kind: "customer_quote",
      title: "Captured customer language",
      excerpt: "We still do this manually every Friday.",
      url: null,
      capturedAt: "2026-07-16T00:00:00.000Z",
      provenance: { assetType: "DISCOVERY_DATA", jsonPointer: "/solution_ideas/0/source_pain" },
    }],
    questions: [{
      questionId,
      consensus,
      skeptic: {
        questionId,
        position: consensus === "contradicted" ? "contradicts" : "insufficient",
        summary: "The current record does not yet support this assumption.",
        subjectKeys: ["I1"],
        evidenceKeys: ["S1"],
        evidenceClass: "observed",
      },
      auditor: {
        questionId,
        position: consensus === "contradicted" ? "contradicts" : "insufficient",
        summary: "More behavioral evidence is required.",
        subjectKeys: ["I1"],
        evidenceKeys: ["S1"],
        evidenceClass: "observed",
      },
    }],
    skepticModel: "skeptic-test",
    auditorModel: "auditor-test",
    promptVersion: 1,
    createdAt: "2026-07-16T00:00:00.000Z",
  };
}

describe("DecisionRiskQueue", () => {
  afterEach(cleanup);

  beforeEach(() => {
    apiMocks.getSelectionChallenges.mockReset();
  });

  it("shows one exact-revision gap per idea and prioritizes contradiction without a numeric score", async () => {
    const signal = idea("idea-signal", "Signal Desk", 3);
    const evidence = idea("idea-evidence", "Evidence Map", 1);
    apiMocks.getSelectionChallenges.mockResolvedValue({
      challenges: [
        challengeFor(signal, "demand", "insufficient", "buyer_will_pay"),
        challengeFor(evidence, "dependencies", "contradicted", "required_data_is_obtainable"),
        challengeFor({ ...signal, idea_revision: 2 }, "demand", "contradicted", "pain_is_observed"),
      ],
      stale: [],
    });
    const onReviewGap = vi.fn();
    const view = render(DecisionRiskQueue, {
      props: { jobId: "job-123", ideas: [signal, evidence], onReviewGap },
    });

    await waitFor(() => expect(view.getByText("2 unresolved")).toBeInTheDocument());
    const rows = [...view.container.querySelectorAll(".risk-list li")];
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent("Evidence Map");
    expect(rows[0]).toHaveTextContent("Contradicted");
    expect(rows[1]).toHaveTextContent("Signal Desk");
    expect(rows[1]).toHaveTextContent("Not established");
    expect(rows[0]).toHaveTextContent("Observed evidence cited");
    expect(view.container).not.toHaveTextContent("risk score");

    await fireEvent.click(view.getAllByRole("button", { name: "Review gap" })[0]);
    expect(onReviewGap).toHaveBeenCalledWith({
      ideaId: "idea-evidence",
      ideaRevision: 1,
      lens: "dependencies",
      challengeId: "idea-evidence-dependencies-contradicted",
      questionId: "required_data_is_obtainable",
    });
  });

  it("keeps stale and unassessed coverage visible instead of inventing a risk", async () => {
    const signal = idea("idea-signal", "Signal Desk", 3);
    const evidence = idea("idea-evidence", "Evidence Map", 1);
    apiMocks.getSelectionChallenges.mockResolvedValue({
      challenges: [],
      stale: [{ ideaId: signal.idea_id, ideaRevision: 3, lens: "distribution" }],
    });
    const onReviewGap = vi.fn();
    const view = render(DecisionRiskQueue, {
      props: { jobId: "job-123", ideas: [signal, evidence], onReviewGap },
    });

    await waitFor(() => expect(view.getByText("Recheck needed")).toBeInTheDocument());
    expect(view.getByText("Reachability changed since the last evidence check.")).toBeInTheDocument();
    expect(view.getByText("Customer demand has not been independently checked.")).toBeInTheDocument();

    await fireEvent.click(view.getAllByRole("button", { name: "Open check" })[0]);
    expect(onReviewGap).toHaveBeenCalledWith({
      ideaId: "idea-signal",
      ideaRevision: 3,
      lens: "distribution",
    });
  });

  it("distinguishes owner-recorded experiment results from generic proxy evidence", async () => {
    const signal = idea("idea-signal", "Signal Desk", 3);
    const challenge = challengeFor(signal, "demand", "insufficient", "buyer_will_pay");
    challenge.evidenceSnapshot = [{
      key: "S1",
      kind: "experiment_result",
      title: "Pricing interview result",
      excerpt: "Three of ten interviewees accepted the target price.",
      url: null,
      capturedAt: "2026-07-16T00:00:00.000Z",
      provenance: {
        assetType: "EXPERIMENT_RESULT",
        experimentId: "experiment-1",
        conclusionId: "conclusion-1",
        originChallengeId: challenge.id,
        evidenceClass: "proxy",
        sourceType: "MANUAL",
        adapterKey: "manual",
        precommitment: {
          primaryMetric: "accepted price",
          passThreshold: "5 of 10",
          failThreshold: "2 or fewer",
          measurementWindow: "7 days",
          sampleTarget: 10,
        },
        observation: {
          observedThrough: "2026-07-16T00:00:00.000Z",
          observationSummary: "Three accepted the price.",
          observedMetric: "3 of 10",
          metrics: [],
          sample: { observed: 10, target: 10, unit: "interviews" },
          limitations: ["Owner-recorded interview notes"],
        },
      },
    }];
    apiMocks.getSelectionChallenges.mockResolvedValue({ challenges: [challenge], stale: [] });

    const view = render(DecisionRiskQueue, {
      props: { jobId: "job-123", ideas: [signal], onReviewGap: vi.fn() },
    });

    await waitFor(() => expect(view.getByText(/Owner-recorded experiment cited/)).toBeInTheDocument());
  });
});
