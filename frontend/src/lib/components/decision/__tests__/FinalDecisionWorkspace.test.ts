import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import FinalDecisionWorkspace from "../FinalDecisionWorkspace.svelte";
import type {
  FinalDecisionLockedTestBrief,
  FinalDecisionLoadResponse,
  SelectionFinalDecision,
} from "$lib/types/finalDecision";
import type { SelectionDecisionHandoff } from "$lib/types/decisionHandoff";

const mocks = vi.hoisted(() => ({
  getFinalDecision: vi.fn(),
  recordFinalDecision: vi.fn(),
  getDecisionHandoff: vi.fn(),
  materializeDecisionHandoff: vi.fn(),
  getGithubConnections: vi.fn(),
  getGithubRepositories: vi.fn(),
  getGithubHandoffDispatch: vi.fn(),
  previewGithubHandoffIssue: vi.fn(),
  dispatchGithubHandoffIssue: vi.fn(),
  reconcileGithubHandoffDispatch: vi.fn(),
}));

vi.mock("$lib/api", async () => {
  class ApiError extends Error {
    constructor(message: string, public status: number) {
      super(message);
    }
  }
  return { ...mocks, ApiError };
});

const sourceFingerprint = "a".repeat(64);
const testExperimentId = "00000000-0000-0000-0000-000000000101";
const challengeId = "00000000-0000-0000-0000-000000000301";

function riskPrompt() {
  return {
    challengeId,
    challengeInputFingerprint: "f".repeat(64),
    challengeArtifactFingerprint: "e".repeat(64),
    ideaId: "idea-signal",
    ideaRevision: 3,
    lens: "demand" as const,
    questionId: "buyer_will_pay",
    consensus: "mixed" as const,
    skeptic: {
      position: "contradicts" as const,
      summary: "Payment intent is not observed in the captured evidence.",
    },
    auditor: {
      position: "mixed" as const,
      summary: "Interview language is only a weak proxy for payment intent.",
    },
  };
}

function lockedTestBrief(
  overrides: Partial<FinalDecisionLockedTestBrief> = {},
): FinalDecisionLockedTestBrief {
  return {
    version: 1,
    experimentId: testExperimentId,
    jobId: "job-1",
    lockedAt: "2026-07-16T11:00:00.000Z",
    idea: {
      ideaId: "idea-signal",
      ideaRevision: 3,
      snapshot: { solution_name: "Signal Desk" },
    },
    origin: null,
    assumption: {
      type: "DESIRABILITY",
      statement: "Qualified buyers will make a payment commitment.",
      whyCritical: "Interest alone does not justify implementation.",
      currentEvidence: "Interview language only.",
    },
    testDesign: {
      method: "PREORDER",
      evidenceSignal: "PAYMENT_INTENT",
      stimulus: "A priced early-access offer.",
      audience: "Qualified operations leads",
      channel: "Interview follow-ups",
      primaryMetric: "Refundable deposits",
      passThreshold: "At least 3 deposits.",
      failThreshold: "No deposits.",
      measurementWindow: "Stop after 15 conversations or 21 days.",
      sampleTarget: 15,
      costEstimate: "$150",
    },
    decisionRules: {
      pass: "Proceed.",
      fail: "Stop or reshape.",
      ambiguous: "Run diagnostic interviews.",
      invalid: "Repair recruitment and rerun.",
    },
    briefFingerprint: "e".repeat(64),
    runStatus: null,
    conclusionId: null,
    ...overrides,
  };
}

function frozenTestBrief() {
  const { runStatus: _runStatus, conclusionId: _conclusionId, ...brief } = lockedTestBrief();
  return { ...brief, runStatusAtDecision: null };
}

function frozenPreMortem() {
  return {
    version: 1 as const,
    target: { ideaId: "idea-signal", ideaRevision: 3 },
    entries: [{
      failureMode: "The audience does not return after the first useful signal.",
      earlyWarningSignal: "Fewer than three of ten trial users return within fourteen days.",
      mitigation: "Interview non-returning users and narrow the recurring workflow before building more.",
      origin: null,
    }],
  };
}

function loadResponse(
  overrides: Partial<FinalDecisionLoadResponse> = {},
): FinalDecisionLoadResponse {
  return {
    decision: null,
    sourceFingerprint,
    recommendation: {
      ideaId: "idea-signal",
      ideaRevision: 3,
      solutionName: "Signal Desk",
      identityResolution: "exact",
      selectionRationale: "Strongest balance of demand and feasibility.",
      verdict: {
        verdict: "Conditional",
        rationale: "Promising if distribution can be proven.",
        risk_level: "Medium",
        primary_concern: "Distribution remains unproven.",
      },
      generatedAt: "2026-07-16T10:00:00.000Z",
      reportEvidence: { role: "recommended" },
    },
    finalists: [
      {
        ideaId: "idea-signal",
        ideaRevision: 3,
        solutionName: "Signal Desk",
        reportEvidence: { role: "recommended" },
      },
      {
        ideaId: "idea-risk",
        ideaRevision: 2,
        solutionName: "Risk Radar",
        reportEvidence: { role: "alternative" },
      },
    ],
    conclusions: [],
    lockedTestBriefs: [],
    riskPrompts: [],
    ...overrides,
  };
}

function decision(overrides: Partial<SelectionFinalDecision> = {}): SelectionFinalDecision {
  return {
    id: "decision-1",
    jobId: "job-1",
    disposition: "PROCEED",
    selectedIdeaId: "idea-signal",
    selectedIdeaRevision: 3,
    testExperimentId: null,
    testExperimentSnapshot: null,
    preMortemSnapshot: frozenPreMortem(),
    recommendationRelation: "FOLLOWED",
    rationale: "This is the clearest next move for the current audience.",
    acceptedRisks: "Distribution remains open.",
    changeCriterion: "Stop if ten qualified calls produce no follow-up requests.",
    overrideReason: null,
    requestFingerprint: "b".repeat(64),
    sourceFingerprint,
    recommendationSnapshot: {},
    selectedIdeaSnapshot: { solution_name: "Signal Desk" },
    createdAt: "2026-07-16T12:00:00.000Z",
    ...overrides,
  };
}

function handoff(overrides: Partial<SelectionDecisionHandoff> = {}): SelectionDecisionHandoff {
  return {
    id: "handoff-1",
    finalDecisionId: "decision-1",
    action: "VALIDATE_MORE",
    ideaId: "idea-signal",
    ideaRevision: 3,
    inputFingerprint: "c".repeat(64),
    artifact: {
      jobId: "job-1",
      finalDecisionId: "decision-1",
      action: "VALIDATE_MORE",
      target: {
        ideaId: "idea-signal",
        ideaRevision: 3,
        title: "Signal Desk",
        problem: "Founders miss repeated buyer signals.",
        audience: "Solo SaaS founders",
        valueProposition: "Collect recurring demand in one place.",
        proposedScope: ["Signal inbox"],
        technicalApproach: null,
        estimatedBuildTime: null,
      },
      decision: {
        disposition: "TEST_FIRST",
        recommendationRelation: "FOLLOWED",
        rationale: "This is the clearest next move for the current audience.",
        acceptedRisks: "Distribution remains open.",
        changeCriterion: "Stop if ten qualified calls produce no follow-up requests.",
        overrideReason: null,
        decidedAt: "2026-07-16T12:00:00.000Z",
      },
      evidence: {
        sourceFingerprint,
        reportSha256: "d".repeat(64),
        recommendationSnapshot: {},
        selectedIdeaSnapshot: { solution_name: "Signal Desk" },
        alternativesSnapshot: {},
        evidenceSnapshot: {
          experimentConclusions: [],
          selectedTestBrief: frozenTestBrief(),
        },
      },
      executionPolicy: {
        providerDispatchAllowed: true,
        allowedOperation: "CREATE_VALIDATION_ISSUE",
        resumeRequiresNewOwnerDecision: false,
        terminal: false,
      },
      testBrief: frozenTestBrief(),
      preMortem: frozenPreMortem(),
    },
    createdAt: "2026-07-16T12:05:00.000Z",
    ...overrides,
  };
}

beforeEach(() => {
  mocks.getDecisionHandoff.mockResolvedValue({ handoff: null });
  mocks.getGithubConnections.mockResolvedValue({ enabled: false, connections: [] });
  mocks.getGithubRepositories.mockResolvedValue([]);
  mocks.getGithubHandoffDispatch.mockResolvedValue(null);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

async function completePreMortem(): Promise<void> {
  await fireEvent.input(screen.getByLabelText("It failed because…"), {
    target: { value: "The audience does not return after the first useful signal." },
  });
  await fireEvent.input(screen.getByLabelText("Earliest observable warning…"), {
    target: { value: "Fewer than three of ten trial users return within fourteen days." },
  });
  await fireEvent.input(screen.getByLabelText("If that appears, I will…"), {
    target: { value: "Interview non-returning users and narrow the recurring workflow before building more." },
  });
}

async function completeDecisionBasis(
  rationale = "This is the clearest next move for the current audience.",
  changeCriterion = "Stop if ten qualified calls produce no follow-up requests.",
): Promise<void> {
  await fireEvent.input(screen.getByLabelText("Why is this the right next move now?"), {
    target: { value: rationale },
  });
  await fireEvent.input(screen.getByLabelText("I will change or stop this decision if…"), {
    target: { value: changeCriterion },
  });
}

async function continueToPreMortem(): Promise<void> {
  await fireEvent.click(screen.getByRole("button", { name: "Continue to pre-mortem" }));
}

async function reviewDecision(): Promise<void> {
  await fireEvent.click(screen.getByRole("button", { name: "Review decision" }));
}

describe("FinalDecisionWorkspace", () => {
  it("keeps editable controls out of the report until the Decision Lab opens", async () => {
    mocks.getFinalDecision.mockResolvedValue(loadResponse());
    const view = render(FinalDecisionWorkspace, { props: { jobId: "job-1", open: false } });

    expect(await view.findByRole("button", { name: "Open Decision Lab" })).toBeInTheDocument();
    expect(view.queryByRole("dialog")).not.toBeInTheDocument();
    expect(view.queryByLabelText("Why is this the right next move now?")).not.toBeInTheDocument();

    await fireEvent.click(view.getByRole("button", { name: "Open Decision Lab" }));
    expect(await view.findByRole("dialog", { name: "Commit to the next move" })).toBeInTheDocument();
  });

  it("guards a dirty draft without opening a nested confirmation dialog", async () => {
    mocks.getFinalDecision.mockResolvedValue(loadResponse());
    const view = render(FinalDecisionWorkspace, { props: { jobId: "job-1", open: true } });
    await view.findByText("Signal Desk");
    await fireEvent.input(view.getByLabelText("Why is this the right next move now?"), {
      target: { value: "This draft is intentionally not finished yet." },
    });

    await fireEvent.click(view.getByRole("button", { name: "Close Commit to the next move" }));
    expect(view.getByText("Discard this draft?")).toBeInTheDocument();
    expect(view.getAllByRole("dialog")).toHaveLength(1);

    await fireEvent.click(view.getByRole("button", { name: "Continue editing" }));
    await fireEvent.click(view.getByRole("button", { name: "Cancel" }));
    await fireEvent.click(view.getByRole("button", { name: "Discard draft" }));
    await waitFor(() => expect(view.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("renders report evidence without claiming an unrecorded test", async () => {
    mocks.getFinalDecision.mockResolvedValue(loadResponse());
    const view = render(FinalDecisionWorkspace, { props: { jobId: "job-1", open: true } });

    expect(await view.findByText("Signal Desk")).toBeInTheDocument();
    expect(view.getByText("Distribution remains unproven.")).toBeInTheDocument();
    expect(view.getByText("No test conclusion was recorded. This does not mean the idea was tested.")).toBeInTheDocument();
    expect(view.queryByText(/idea validated/i)).not.toBeInTheDocument();
  });

  it("blocks a target decision until a complete pre-mortem is written", async () => {
    mocks.getFinalDecision.mockResolvedValue(loadResponse());
    const view = render(FinalDecisionWorkspace, { props: { jobId: "job-1", open: true } });
    await view.findByText("Signal Desk");
    await completeDecisionBasis();
    await continueToPreMortem();
    expect(view.getByRole("button", { name: "Review decision" })).toBeDisabled();
  });

  it("uses a current saved risk as exact editable provenance", async () => {
    mocks.getFinalDecision.mockResolvedValue(loadResponse({ riskPrompts: [riskPrompt()] }));
    mocks.recordFinalDecision.mockResolvedValue(decision());
    const view = render(FinalDecisionWorkspace, { props: { jobId: "job-1", open: true } });
    await view.findByText("Signal Desk");
    await completeDecisionBasis();
    await continueToPreMortem();

    await fireEvent.change(view.getByLabelText("Start from a saved risk"), {
      target: { value: `${challengeId}:buyer_will_pay` },
    });
    expect(view.getByLabelText("It failed because…")).toHaveValue(
      "The assumption failed: Qualified buyers will make a concrete payment commitment for this outcome.",
    );
    await fireEvent.input(view.getByLabelText("Earliest observable warning…"), {
      target: { value: "No qualified buyer places a deposit in the first fifteen conversations." },
    });
    await fireEvent.input(view.getByLabelText("If that appears, I will…"), {
      target: { value: "Stop implementation and reshape the paid outcome before collecting more demand." },
    });
    await reviewDecision();
    await fireEvent.click(view.getByRole("button", { name: "Record decision" }));

    await waitFor(() => expect(mocks.recordFinalDecision).toHaveBeenCalledWith(
      "job-1",
      expect.objectContaining({
        preMortem: [expect.objectContaining({
          origin: { challengeId, questionId: "buyer_will_pay" },
        })],
      }),
    ));
  });

  it("clears exact-revision pre-mortem entries when the finalist changes", async () => {
    mocks.getFinalDecision.mockResolvedValue(loadResponse());
    const view = render(FinalDecisionWorkspace, { props: { jobId: "job-1", open: true } });
    await view.findByText("Signal Desk");
    await completeDecisionBasis();
    await continueToPreMortem();
    await completePreMortem();
    await fireEvent.click(view.getByRole("button", { name: /Back/ }));
    await fireEvent.change(view.getByLabelText("Idea to carry forward"), {
      target: { value: "idea-risk:2" },
    });
    await fireEvent.input(await view.findByLabelText("Why are you overriding the research recommendation?"), {
      target: { value: "The founder already owns the alternate distribution channel." },
    });
    await continueToPreMortem();
    expect(view.getByLabelText("It failed because…")).toHaveValue("");
    expect(view.getByText("The candidate changed. Its pre-mortem was cleared.")).toBeInTheDocument();
  });

  it("uses a second confirmation and records the exact recommended revision", async () => {
    mocks.getFinalDecision.mockResolvedValue(loadResponse());
    mocks.recordFinalDecision.mockResolvedValue(decision());
    const view = render(FinalDecisionWorkspace, { props: { jobId: "job-1", open: true } });

    await view.findByText("Signal Desk");
    await completeDecisionBasis();
    await continueToPreMortem();
    await completePreMortem();
    await reviewDecision();
    expect(mocks.recordFinalDecision).not.toHaveBeenCalled();

    await fireEvent.click(view.getByRole("button", { name: "Record decision" }));
    await waitFor(() => expect(mocks.recordFinalDecision).toHaveBeenCalledWith(
      "job-1",
      expect.objectContaining({
        disposition: "PROCEED",
        ideaId: "idea-signal",
        ideaRevision: 3,
        sourceFingerprint,
      }),
    ));
    expect(await view.findByText("Your commitment")).toBeInTheDocument();
    expect(view.getByText(/does not label the idea validated/i)).toBeInTheDocument();
  });

  it("requires and submits an override reason for another finalist", async () => {
    mocks.getFinalDecision.mockResolvedValue(loadResponse());
    mocks.recordFinalDecision.mockResolvedValue(decision({
      selectedIdeaId: "idea-risk",
      selectedIdeaRevision: 2,
      recommendationRelation: "OVERRIDDEN",
      overrideReason: "The founder already owns the alternate distribution channel.",
      selectedIdeaSnapshot: { solution_name: "Risk Radar" },
    }));
    const view = render(FinalDecisionWorkspace, { props: { jobId: "job-1", open: true } });

    await view.findByText("Signal Desk");
    await fireEvent.change(view.getByLabelText("Idea to carry forward"), {
      target: { value: "idea-risk:2" },
    });
    const override = await view.findByLabelText("Why are you overriding the research recommendation?");
    await fireEvent.input(override, {
      target: { value: "The founder already owns the alternate distribution channel." },
    });
    await completeDecisionBasis(
      "This route better fits the assets already available.",
      "Change direction if the first five users cannot complete the workflow.",
    );
    await continueToPreMortem();
    await completePreMortem();
    await reviewDecision();
    await fireEvent.click(view.getByRole("button", { name: "Record decision" }));

    await waitFor(() => expect(mocks.recordFinalDecision).toHaveBeenCalledWith(
      "job-1",
      expect.objectContaining({
        ideaId: "idea-risk",
        ideaRevision: 2,
        overrideReason: "The founder already owns the alternate distribution channel.",
      }),
    ));
  });

  it("requires and submits the exact locked brief for Test first", async () => {
    const brief = lockedTestBrief();
    mocks.getFinalDecision.mockResolvedValue(loadResponse({ lockedTestBriefs: [brief] }));
    mocks.recordFinalDecision.mockResolvedValue(decision({
      disposition: "TEST_FIRST",
      testExperimentId,
      testExperimentSnapshot: frozenTestBrief(),
    }));
    const view = render(FinalDecisionWorkspace, { props: { jobId: "job-1", open: true } });

    await view.findByText("Signal Desk");
    await fireEvent.click(view.getByRole("radio", { name: /^Test first/ }));
    expect(await view.findByText(/Desirability · Qualified buyers will make a payment commitment/)).toBeInTheDocument();
    await completeDecisionBasis(
      "This is the highest-risk assumption and must be tested before building.",
      "Stop if the precommitted fail threshold is reached.",
    );
    await continueToPreMortem();
    await completePreMortem();
    await reviewDecision();
    expect(view.getByText(`“${brief.assumption.statement}”`)).toBeInTheDocument();
    await fireEvent.click(view.getByRole("button", { name: "Record decision" }));

    await waitFor(() => expect(mocks.recordFinalDecision).toHaveBeenCalledWith(
      "job-1",
      expect.objectContaining({
        disposition: "TEST_FIRST",
        ideaId: "idea-signal",
        ideaRevision: 3,
        testExperimentId,
      }),
    ));
  });

  it("blocks Test first when no locked brief matches the exact finalist revision", async () => {
    mocks.getFinalDecision.mockResolvedValue(loadResponse({ lockedTestBriefs: [] }));
    const view = render(FinalDecisionWorkspace, { props: { jobId: "job-1", open: true } });
    await view.findByText("Signal Desk");
    await fireEvent.click(view.getByRole("radio", { name: /^Test first/ }));
    expect(await view.findByText(/No locked test brief matches Signal Desk/)).toBeInTheDocument();
    expect(view.getByRole("button", { name: "Continue to pre-mortem" })).toBeDisabled();
  });

  it("does not attach a pre-mortem to Park", async () => {
    mocks.getFinalDecision.mockResolvedValue(loadResponse());
    mocks.recordFinalDecision.mockResolvedValue(decision({
      disposition: "PARK",
      selectedIdeaId: null,
      selectedIdeaRevision: null,
      selectedIdeaSnapshot: null,
      preMortemSnapshot: null,
      recommendationRelation: "DEFERRED",
    }));
    const view = render(FinalDecisionWorkspace, { props: { jobId: "job-1", open: true } });
    await view.findByText("Signal Desk");
    await fireEvent.click(view.getByRole("radio", { name: /^Park/ }));
    expect(view.queryByLabelText("It failed because…")).not.toBeInTheDocument();
    await completeDecisionBasis(
      "The evidence is useful but the timing does not support an active commitment.",
      "Revisit when a qualified distribution partner is available.",
    );
    await reviewDecision();
    await fireEvent.click(view.getByRole("button", { name: "Record decision" }));
    await waitFor(() => expect(mocks.recordFinalDecision).toHaveBeenCalledWith(
      "job-1",
      expect.not.objectContaining({ preMortem: expect.anything() }),
    ));
  });

  it("renders an existing decision as a read-only owner receipt", async () => {
    mocks.getFinalDecision.mockResolvedValue(loadResponse({
      decision: decision({ disposition: "TEST_FIRST" }),
    }));
    const view = render(FinalDecisionWorkspace, { props: { jobId: "job-1", open: true } });

    expect(await view.findByText("Read-only")).toBeInTheDocument();
    expect(view.getAllByText(/Test first/).length).toBeGreaterThan(0);
    expect(view.getByText("This is the clearest next move for the current audience.")).toBeInTheDocument();
    expect(view.getByText("Earliest warning: Fewer than three of ten trial users return within fourteen days.")).toBeInTheDocument();
    expect(view.queryByRole("button", { name: "Review owner decision" })).not.toBeInTheDocument();
  });

  it("creates and previews a deterministic test-first handoff inside the protected memo", async () => {
    const recordedDecision = decision({
      disposition: "TEST_FIRST",
      testExperimentId,
      testExperimentSnapshot: frozenTestBrief(),
    });
    mocks.getFinalDecision.mockResolvedValue(loadResponse({ decision: recordedDecision }));
    mocks.materializeDecisionHandoff.mockResolvedValue(handoff());
    const view = render(FinalDecisionWorkspace, { props: { jobId: "job-1", open: true } });

    await fireEvent.click(await view.findByRole("button", { name: "Create test handoff" }));

    await waitFor(() => expect(mocks.materializeDecisionHandoff).toHaveBeenCalledWith(
      "job-1",
      recordedDecision.id,
    ));
    expect(await view.findByRole("heading", { name: "Test handoff" })).toBeInTheDocument();
    expect(view.getByText("idea-signal · revision 3")).toBeInTheDocument();
    expect(view.getAllByText("Qualified buyers will make a payment commitment.").length).toBeGreaterThan(0);
    expect(view.getByRole("link", { name: "Download .md" })).toHaveAttribute(
      "href",
      "/api/jobs/job-1/decision-handoff/export/md",
    );
    expect(view.getByText(/does not claim validation/i)).toBeInTheDocument();
  });
});
