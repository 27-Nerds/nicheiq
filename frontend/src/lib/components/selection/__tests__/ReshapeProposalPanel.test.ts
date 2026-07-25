import { cleanup, fireEvent, render, waitFor } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ReshapeProposalPanel, {
  type ReshapeSource,
} from "../ReshapeProposalPanel.svelte";
import type {
  ExperimentNarrowingProposalResponse,
  IdeaSynthesisPatch,
} from "$lib/api";
import type { FounderFitArtifact, FounderFitResult } from "$lib/types/founderFit";
import type { SolutionPreview } from "$lib/types/job";
import type { SelectionExperiment } from "$lib/types/selectionExperiment";

// ── Shared child patch ──
const patch: IdeaSynthesisPatch = {
  kind: "idea_synthesis",
  operation: "narrow",
  proposedTitle: "Weekly Signal Brief",
  proposedBrief: "One weekly review for a single renewal-risk workflow.",
  changeSummary: "Removes continuous monitoring and secondary workflows.",
  rationale: "Designed around the recorded time conflict.",
  parents: [
    {
      ideaId: "idea-parent",
      ideaRevision: 2,
      solutionName: "Signal Desk",
      contribution: "Keep the signal interpretation workflow.",
    },
  ],
  evidence: {
    sourceAnchors: [
      { ideaId: "idea-parent", ideaRevision: 2, candidateSnapshotSha256: "a".repeat(64) },
    ],
    requiresValidation: [
      "Does not transfer automatically: continuous monitoring demand.",
      "New assumption: a weekly review is timely enough.",
    ],
  },
  newAssumptions: ["A weekly review is timely enough."],
};

function response(
  state: NonNullable<ExperimentNarrowingProposalResponse["settlement"]>["state"] = "ready",
  messageId = "reshape-proposal-1",
  parentRevision = 2,
): ExperimentNarrowingProposalResponse {
  return {
    proposalMessage: {
      id: messageId,
      content: "One smaller variant.",
      patchJson: patch,
      createdAt: "2026-07-16T01:00:00.000Z",
    },
    settlement: {
      state,
      idea:
        state === "accepted"
          ? {
              solution_name: "Weekly Signal Brief",
              idea_id: "idea-child",
              idea_revision: 1,
              synthesis_operation: "narrow" as const,
              synthesis_source_message_id: messageId,
              synthesized_from: [{ idea_id: "idea-parent", idea_revision: parentRevision }],
            }
          : null,
    },
  };
}

// ── Founder-fit source fixtures ──
const idea = {
  idea_id: "idea-parent",
  idea_revision: 2,
  solution_name: "Signal Desk",
  description: "An always-on signal monitoring workflow.",
} as SolutionPreview;

const founderFitResult = {
  ideaId: "idea-parent",
  ideaRevision: 2,
  ideaTitle: "Signal Desk",
  verdict: "needs_reshape",
  summary: "The first slice is too broad.",
  strongestAdvantage: "The founder can write for the audience.",
  blockingConflict: null,
  decisionChangingUnknown: "Whether one useful path fits in a weekend.",
  sensitivity: "Remove continuous monitoring.",
  dimensions: [
    {
      dimension: "time",
      status: "conflict",
      summary: "The current build exceeds the available weekly time.",
      profileFields: ["weeklyTime"],
      ideaFields: ["estimated_development_time"],
    },
  ],
  suggestedExperiment: {} as never,
} satisfies FounderFitResult;

const artifact = {
  version: 1,
  inputFingerprint: "f".repeat(64),
  profileSnapshot: {} as never,
  ideaSnapshots: [{ idea_id: "idea-parent", idea_revision: 2, solution_name: "Signal Desk" }],
  model: "gpt-test",
  createdAt: "2026-07-16T00:00:00.000Z",
  results: [founderFitResult],
} satisfies FounderFitArtifact;

const founderFitSource: ReshapeSource = {
  kind: "founderFit",
  idea,
  artifact,
  result: founderFitResult,
};

// ── Experiment source fixtures ──
const experiment: SelectionExperiment = {
  id: "experiment-1",
  jobId: "job-1",
  ideaId: "idea-parent",
  ideaRevision: 3,
  ideaSnapshot: {
    solution_name: "Signal Desk",
    value_proposition: "A broad dashboard for recurring demand signals.",
  },
  status: "LOCKED",
  assumptionType: "DESIRABILITY",
  assumption: "Operators will commit to the broad dashboard.",
  whyCritical: "Without commitment this positioning should change.",
  currentEvidence: "Complaint language only.",
  method: "CUSTOMER_INTERVIEWS",
  evidenceSignal: "STATED_PREFERENCE",
  stimulus: "A broad dashboard concept.",
  audience: "Operations leads",
  channel: "Interviews",
  primaryMetric: "Paid pilots",
  passThreshold: "3 pilots",
  failThreshold: "0 pilots",
  measurementWindow: "14 days",
  sampleTarget: 12,
  costEstimate: "",
  passAction: "Continue",
  failAction: "Narrow the idea",
  flatAction: "Narrow and repeat",
  invalidAction: "Repair the test",
  lockedAt: "2026-07-15T00:00:00.000Z",
  createdAt: "2026-07-14T00:00:00.000Z",
  updatedAt: "2026-07-15T00:00:00.000Z",
  conclusion: {
    id: "conclusion-1",
    experimentId: "experiment-1",
    ideaId: "idea-parent",
    ideaRevision: 3,
    outcome: "FAIL",
    evidenceSource: "MANUAL",
    requestFingerprint: "fingerprint",
    ownerRationale: "No participant would commit.",
    nextActionSnapshot: "Narrow the idea",
    snapshot: {
      schemaVersion: 1,
      experiment: {},
      precommitment: {},
      evidence: {},
      adjudication: {},
    },
    concludedByUserId: "owner-1",
    createdAt: "2026-07-16T00:00:00.000Z",
  },
};

const experimentSource: ReshapeSource = { kind: "experiment", experiment };

afterEach(cleanup);

describe("ReshapeProposalPanel · founderFit", () => {
  it("shows the frozen conflict and requires a second click before paid evaluation", async () => {
    const onEvaluate = vi.fn().mockResolvedValue(true);
    const createProposal = vi.fn().mockResolvedValue(response());
    const fetchProposal = vi.fn().mockResolvedValue(response());
    const view = render(ReshapeProposalPanel, {
      props: { source: founderFitSource, seedCost: 3, createProposal, fetchProposal, onEvaluate },
    });

    await fireEvent.click(view.getByRole("button", { name: "Reshape to fit" }));
    expect(
      view.getByRole("dialog", {
        name: "Make the product shape smaller, not the evidence stronger",
      }),
    ).toBeInTheDocument();
    expect(
      await view.findByText("The current build exceeds the available weekly time."),
    ).toBeInTheDocument();
    expect(view.getByText("Weekly Signal Brief")).toBeInTheDocument();
    expect(
      view.getByText(/Parent evidence and scores do not transfer automatically/),
    ).toBeInTheDocument();

    await fireEvent.click(view.getByRole("button", { name: /Evaluate variant/ }));
    expect(onEvaluate).not.toHaveBeenCalled();
    await fireEvent.click(view.getByRole("button", { name: "Confirm independent evaluation" }));
    await waitFor(() => expect(onEvaluate).toHaveBeenCalledWith(patch, "reshape-proposal-1"));
  });

  it("restores an accepted child and exposes exact comparison/adoption actions", async () => {
    const createProposal = vi.fn().mockResolvedValue(response("accepted"));
    const fetchProposal = vi.fn().mockResolvedValue(response("accepted"));
    const onReview = vi.fn().mockReturnValue({ ok: true });
    const onUse = vi.fn().mockReturnValue({ ok: true, message: "Variant is now in your shortlist." });
    const view = render(ReshapeProposalPanel, {
      props: {
        source: founderFitSource,
        seedCost: 3,
        createProposal,
        fetchProposal,
        onEvaluate: vi.fn(),
        onReview,
        onUse,
      },
    });

    await fireEvent.click(view.getByRole("button", { name: "Reshape to fit" }));
    await fireEvent.click(await view.findByRole("button", { name: "Compare with parent" }));
    expect(onReview).toHaveBeenCalledWith(
      patch,
      expect.objectContaining({ idea_id: "idea-child" }),
      "reshape-proposal-1",
    );
    await fireEvent.click(view.getByRole("button", { name: "Reshape to fit" }));
    await fireEvent.click(view.getByRole("button", { name: "Use variant in shortlist" }));
    expect(onUse).toHaveBeenCalledWith(
      patch,
      expect.objectContaining({ idea_id: "idea-child" }),
      "reshape-proposal-1",
    );
  });
});

describe("ReshapeProposalPanel · experiment", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows an exact before/after ledger and requires a second click before evaluation", async () => {
    const onEvaluate = vi.fn().mockResolvedValue(true);
    const createProposal = vi.fn().mockResolvedValue(response("ready", "proposal-message-1", 3));
    const fetchProposal = vi.fn().mockResolvedValue(response("ready", "proposal-message-1", 3));
    const view = render(ReshapeProposalPanel, {
      props: { source: experimentSource, seedCost: 2, createProposal, fetchProposal, onEvaluate },
    });

    await fireEvent.click(view.getByRole("button", { name: "Narrow this idea" }));
    expect(
      view.getByRole("dialog", { name: "Turn this result into one sharper candidate" }),
    ).toBeInTheDocument();

    expect(await view.findByText("Before · parent rev 3")).toBeInTheDocument();
    expect(
      view.getByText("A broad dashboard for recurring demand signals."),
    ).toBeInTheDocument();
    expect(view.getByText("After · unevaluated child")).toBeInTheDocument();
    expect(view.getByText(patch.proposedTitle)).toBeInTheDocument();
    expect(view.getByText("Keep the signal interpretation workflow.")).toBeInTheDocument();
    expect(view.getByText(/scores do not transfer/i)).toBeInTheDocument();

    await fireEvent.click(view.getByRole("button", { name: /Evaluate variant/ }));
    expect(onEvaluate).not.toHaveBeenCalled();
    await fireEvent.click(view.getByRole("button", { name: "Confirm independent evaluation" }));

    await waitFor(() => expect(onEvaluate).toHaveBeenCalledWith(patch, "proposal-message-1"));
    expect(await view.findByText("Evaluating independently…")).toBeInTheDocument();
  });

  it("restores an accepted receipt without re-arming evaluation", async () => {
    const onEvaluate = vi.fn().mockResolvedValue(true);
    const createProposal = vi.fn().mockResolvedValue(response("accepted", "proposal-message-1", 3));
    const fetchProposal = vi.fn().mockResolvedValue(response("accepted", "proposal-message-1", 3));
    const view = render(ReshapeProposalPanel, {
      props: { source: experimentSource, seedCost: 2, createProposal, fetchProposal, onEvaluate },
    });

    await fireEvent.click(view.getByRole("button", { name: "Narrow this idea" }));
    expect(await view.findByText("Evaluated. Added to ranked ideas.")).toBeInTheDocument();
    expect(view.queryByRole("button", { name: /Evaluate variant/ })).not.toBeInTheDocument();
    expect(onEvaluate).not.toHaveBeenCalled();
  });

  it("offers exact parent comparison and shortlist adoption for an accepted child", async () => {
    const accepted = response("accepted", "proposal-message-1", 3);
    const createProposal = vi.fn().mockResolvedValue(accepted);
    const fetchProposal = vi.fn().mockResolvedValue(accepted);
    const onEvaluate = vi.fn().mockResolvedValue(true);
    const onReview = vi.fn().mockReturnValue({ ok: true });
    const onUse = vi.fn().mockReturnValue({ ok: true });
    const view = render(ReshapeProposalPanel, {
      props: {
        source: experimentSource,
        seedCost: 2,
        createProposal,
        fetchProposal,
        onEvaluate,
        onReview,
        onUse,
      },
    });

    await fireEvent.click(view.getByRole("button", { name: "Narrow this idea" }));
    await fireEvent.click(await view.findByRole("button", { name: "Compare with parent" }));
    await fireEvent.click(view.getByRole("button", { name: "Narrow this idea" }));
    await fireEvent.click(view.getByRole("button", { name: "Use variant in shortlist" }));

    const child = accepted.settlement?.idea;
    expect(child).not.toBeNull();
    expect(onReview).toHaveBeenCalledWith(patch, child, "proposal-message-1");
    expect(onUse).toHaveBeenCalledWith(patch, child, "proposal-message-1");
  });
});
