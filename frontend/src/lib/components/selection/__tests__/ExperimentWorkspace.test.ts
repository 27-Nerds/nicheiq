import { cleanup, fireEvent, render, waitFor, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import ExperimentWorkspace from "../ExperimentWorkspace.svelte";
import type { SelectionExperiment, SelectionExperimentDraft } from "$lib/types/selectionExperiment";
import type { SolutionPreview } from "$lib/types/job";

const mocks = vi.hoisted(() => ({
  getSelectionExperiments: vi.fn(),
  createSelectionExperiment: vi.fn(),
  updateSelectionExperiment: vi.fn(),
  lockSelectionExperiment: vi.fn(),
  launchSelectionExperiment: vi.fn(),
  closeSelectionExperimentRun: vi.fn(),
  getSelectionExperimentResults: vi.fn(),
  concludeSelectionExperiment: vi.fn(),
}));

vi.mock("$lib/api", () => mocks);

const idea: SolutionPreview = {
  idea_id: "idea-signal",
  idea_revision: 3,
  solution_name: "Signal Desk",
  headline: "Signal Desk for operators",
  description: "Find recurring buyer signals",
  value_proposition: "Helps operators choose what to build next",
  source_pain: "Operators miss recurring demand signals",
  source_segment: "Operations leads at service businesses",
  critic_concern: "Buyer urgency has not been demonstrated behaviorally",
  market_fit_score: 0.6,
  technical_feasibility_score: 0.7,
  estimated_development_time: "4–6 weeks",
};

const idea2: SolutionPreview = {
  idea_id: "idea-ledger",
  idea_revision: 1,
  solution_name: "Ledger Watch",
  headline: "Ledger Watch for bookkeepers",
  description: "Flag duplicate vendor entries",
  value_proposition: "Helps bookkeepers catch duplicate spend before it posts",
  source_pain: "Bookkeepers miss duplicate vendor charges",
  source_segment: "Independent bookkeepers",
  critic_concern: "Duplicate-catch value has not been demonstrated behaviorally",
  market_fit_score: 0.5,
  technical_feasibility_score: 0.6,
  estimated_development_time: "3–5 weeks",
};

const completedDraft: SelectionExperimentDraft = {
  ideaId: "idea-signal",
  ideaRevision: 3,
  originChallengeId: null,
  originQuestionId: null,
  assumptionType: "DESIRABILITY",
  assumption: "Buyer urgency has not been demonstrated behaviorally",
  whyCritical: "Helps operators choose what to build next",
  currentEvidence: "Operators miss recurring demand signals",
  method: "CTA_SMOKE_TEST",
  evidenceSignal: "CTA_INTEREST",
  stimulus: "A focused test of Signal Desk for operators with one observable next step.",
  audience: "Operations leads at service businesses",
  channel: "Two operator communities",
  primaryMetric: "Qualified CTA clicks divided by qualified unique visitors",
  passThreshold: "At least 8% after 150 qualified visitors",
  failThreshold: "Below 3% after 150 qualified visitors",
  measurementWindow: "14 days or 150 qualified visitors, whichever is later",
  sampleTarget: null,
  costEstimate: "",
  passAction: "Continue to a concierge test",
  failAction: "Park this positioning",
  flatAction: "Revise the offer once and repeat",
  invalidAction: "Repair targeting or instrumentation and rerun",
};

function experiment(overrides: Partial<SelectionExperiment> = {}): SelectionExperiment {
  return {
    id: "experiment-1",
    jobId: "job-1",
    ideaSnapshot: { solution_name: "Signal Desk", headline: "Signal Desk for operators" },
    status: "DRAFT",
    lockedAt: null,
    createdAt: "2026-07-15T00:00:00.000Z",
    updatedAt: "2026-07-15T00:00:00.000Z",
    run: null,
    ...completedDraft,
    ...overrides,
  };
}

describe("ExperimentWorkspace", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("isolates a load failure and offers a retry without blocking the selection flow", async () => {
    mocks.getSelectionExperiments
      .mockRejectedValueOnce(new Error("gateway returned HTML"))
      .mockResolvedValueOnce([]);
    const view = render(ExperimentWorkspace, { props: { jobId: "job-1", ideas: [idea] } });

    expect(await view.findByText("Tests are temporarily unavailable.")).toBeInTheDocument();
    expect(view.getByText("Your shortlist and Deep Research are unaffected.")).toBeInTheDocument();

    await fireEvent.click(view.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(mocks.getSelectionExperiments).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(view.queryByText("Tests are temporarily unavailable.")).not.toBeInTheDocument());
  });

  it("anchors an empty workspace to the challenge flow with a draft fallback", async () => {
    mocks.getSelectionExperiments.mockResolvedValue([]);
    const onOpenChallenge = vi.fn();
    const view = render(ExperimentWorkspace, {
      props: { jobId: "job-1", ideas: [idea], onOpenChallenge },
    });

    expect(await view.findByText("No test briefs yet")).toBeInTheDocument();
    await fireEvent.click(view.getByRole("button", { name: "Challenge the evidence" }));
    expect(onOpenChallenge).toHaveBeenCalledOnce();

    const emptyState = view.getByText("No test briefs yet").closest(".empty-state") as HTMLElement;
    await fireEvent.click(within(emptyState).getByRole("button", { name: "Plan a test" }));
    expect(view.getByRole("dialog", { name: "Plan a test" })).toBeInTheDocument();
  });

  it("omits the challenge entry from the empty state when no challenge path is wired", async () => {
    mocks.getSelectionExperiments.mockResolvedValue([]);
    const view = render(ExperimentWorkspace, { props: { jobId: "job-1", ideas: [idea] } });

    expect(await view.findByText("No test briefs yet")).toBeInTheDocument();
    expect(view.queryByRole("button", { name: "Challenge the evidence" })).not.toBeInTheDocument();
  });

  it("creates a precommitted draft against the exact idea revision", async () => {
    mocks.getSelectionExperiments.mockResolvedValue([]);
    mocks.createSelectionExperiment.mockResolvedValue(experiment());
    const view = render(ExperimentWorkspace, { props: { jobId: "job-1", ideas: [idea] } });

    await fireEvent.click(await view.findByRole("button", { name: "Plan a test" }));
    expect(view.getByRole("dialog", { name: "Plan a test" })).toBeInTheDocument();
    expect(view.getByText("Shows interest in the message or entry point.")).toBeInTheDocument();

    const fill = async (label: string, value: string) => {
      await fireEvent.input(view.getByLabelText(label, { exact: false }), { target: { value } });
    };
    await fill("Recruitment or traffic channel", completedDraft.channel);
    await fill("Primary behavioral metric, including numerator and denominator", completedDraft.primaryMetric);
    await fill("Pass at", completedDraft.passThreshold);
    await fill("Fail below", completedDraft.failThreshold);
    await fill("Measurement window and stopping rule", completedDraft.measurementWindow);
    await fill("If it passes", completedDraft.passAction);
    await fill("If it fails", completedDraft.failAction);
    await fill("If it is flat", completedDraft.flatAction);
    await fill("If it is invalid", completedDraft.invalidAction);

    await fireEvent.click(view.getByRole("button", { name: "Save draft" }));

    await waitFor(() => expect(mocks.createSelectionExperiment).toHaveBeenCalledOnce());
    expect(mocks.createSelectionExperiment).toHaveBeenCalledWith("job-1", completedDraft);
    expect(await view.findByText("Buyer urgency has not been demonstrated behaviorally")).toBeInTheDocument();
  });

  it("opens a founder-fit suggestion as an unsaved owner-editable draft", async () => {
    mocks.getSelectionExperiments.mockResolvedValue([]);
    mocks.createSelectionExperiment.mockResolvedValue(experiment());

    const view = render(ExperimentWorkspace, {
      props: {
        jobId: "job-1",
        ideas: [idea],
        prefill: { requestId: "fit-1", draft: completedDraft },
      },
    });

    const assumption = await view.findByLabelText("One atomic assumption that must be true", { exact: false });
    expect(assumption).toHaveValue(completedDraft.assumption);
    expect(mocks.createSelectionExperiment).not.toHaveBeenCalled();

    await fireEvent.click(view.getByRole("button", { name: "Save draft" }));
    await waitFor(() => expect(mocks.createSelectionExperiment).toHaveBeenCalledWith("job-1", completedDraft));
  });

  it("opens a copilot prefill clean so the first close dismisses without a discard warning", async () => {
    mocks.getSelectionExperiments.mockResolvedValue([]);
    const view = render(ExperimentWorkspace, {
      props: {
        jobId: "job-1",
        ideas: [idea],
        prefill: { requestId: "fit-clean", draft: completedDraft },
      },
    });

    const dialog = await view.findByRole("dialog", { name: "Plan a test" });
    await fireEvent.keyDown(dialog, { key: "Escape" });

    await waitFor(() =>
      expect(view.queryByRole("dialog", { name: "Plan a test" })).not.toBeInTheDocument(),
    );
    expect(
      view.queryByText("You have unsaved changes. Close again to discard them."),
    ).not.toBeInTheDocument();
  });

  it("merges a challenge seed with exact-candidate defaults without saving", async () => {
    mocks.getSelectionExperiments.mockResolvedValue([]);
    const view = render(ExperimentWorkspace, {
      props: {
        jobId: "job-1",
        ideas: [idea],
        prefill: {
          requestId: "challenge-1",
          draft: {
            ideaId: "idea-signal",
            ideaRevision: 3,
            originChallengeId: "challenge-1",
            originQuestionId: "pain_is_observed",
            assumptionType: "DESIRABILITY",
            assumption: "Qualified buyers repeatedly experience this pain.",
            whyCritical: "The challenge remains disputed.",
            currentEvidence: "Challenge challenge-1 · question pain_is_observed",
            method: "CUSTOMER_INTERVIEWS",
            evidenceSignal: "LANGUAGE",
          },
        },
      },
    });

    expect(await view.findByLabelText("One atomic assumption that must be true", { exact: false })).toHaveValue(
      "Qualified buyers repeatedly experience this pain.",
    );
    expect(view.getByText("Evidence gap")).toBeInTheDocument();
    expect(view.getByLabelText("Qualified audience", { exact: false })).toHaveValue("Operations leads at service businesses");
    expect(view.getByLabelText("Exact stimulus, offer, prototype, or task", { exact: false })).toHaveValue(
      "A focused test of Signal Desk for operators with one observable next step.",
    );
    const saveButton = view.getByRole("button", { name: "Save draft" });
    expect(saveButton).not.toBeDisabled();
    await fireEvent.click(saveButton);
    expect(mocks.createSelectionExperiment).not.toHaveBeenCalled();
  });

  it("rejects a challenge seed for an older idea revision", async () => {
    mocks.getSelectionExperiments.mockResolvedValue([]);
    const view = render(ExperimentWorkspace, {
      props: {
        jobId: "job-1",
        ideas: [idea],
        prefill: {
          requestId: "challenge-stale",
          draft: { ideaId: "idea-signal", ideaRevision: 2 },
        },
      },
    });

    expect(await view.findByText(/older candidate revision/i)).toBeInTheDocument();
    expect(view.queryByRole("button", { name: "Save draft" })).not.toBeInTheDocument();
  });

  it("requires an explicit second action before locking the brief", async () => {
    mocks.getSelectionExperiments.mockResolvedValue([experiment()]);
    mocks.lockSelectionExperiment.mockResolvedValue(experiment({
      status: "LOCKED",
      lockedAt: "2026-07-15T12:00:00.000Z",
    }));
    const view = render(ExperimentWorkspace, { props: { jobId: "job-1", ideas: [idea] } });

    const lockButton = await view.findByRole("button", { name: "Lock brief" });
    await fireEvent.click(lockButton);
    expect(mocks.lockSelectionExperiment).not.toHaveBeenCalled();
    await fireEvent.click(view.getByRole("button", { name: "Lock brief" }));

    await waitFor(() => expect(mocks.lockSelectionExperiment).toHaveBeenCalledWith("job-1", "experiment-1"));
    expect(await view.findByText("Test brief locked")).toBeInTheDocument();
  });

  it("exposes portable Markdown and JSON only for a locked provenance-preserving brief", async () => {
    mocks.getSelectionExperiments.mockResolvedValue([experiment({
      status: "LOCKED",
      lockedAt: "2026-07-16T12:00:00.000Z",
      originChallengeId: "challenge-1",
      originQuestionId: "pain_is_observed",
      originSnapshot: {
        version: 1,
        kind: "SELECTION_CHALLENGE_QUESTION",
        challengeId: "challenge-1",
        challengeInputFingerprint: "f".repeat(64),
        questionId: "pain_is_observed",
        lens: "demand",
        consensus: "insufficient",
        evidenceKeys: ["S1"],
        skeptic: {
          questionId: "pain_is_observed",
          position: "insufficient",
          summary: "The packet is incomplete.",
          subjectKeys: ["I1"],
          evidenceKeys: ["S1"],
          evidenceClass: "observed",
        },
        auditor: {
          questionId: "pain_is_observed",
          position: "insufficient",
          summary: "More behavior is required.",
          subjectKeys: ["I1"],
          evidenceKeys: ["S1"],
          evidenceClass: "observed",
        },
        citedSources: [{
          key: "S1",
          kind: "customer_quote",
          title: "Operator interview",
          excerpt: "We do this manually.",
          url: null,
          capturedAt: null,
          provenance: { assetType: "DISCOVERY_DATA", jsonPointer: "/interviews/0" },
        }],
      },
    })]);
    const view = render(ExperimentWorkspace, { props: { jobId: "job-1", ideas: [idea] } });

    await fireEvent.click(await view.findByText("View portable test brief"));
    expect(view.getByText("Is the pain directly observed?")).toBeInTheDocument();
    expect(view.getByText(/Evidence review recorded Not established with 1 cited source/)).toBeInTheDocument();
    expect(view.getByRole("link", { name: "Download .md" })).toHaveAttribute(
      "href",
      "/api/jobs/job-1/selection-experiments/experiment-1/export/md",
    );
    expect(view.getByRole("link", { name: "Download JSON" })).toHaveAttribute(
      "href",
      "/api/jobs/job-1/selection-experiments/experiment-1/export/json",
    );
  });

  it("reviews and publishes an immutable public test", async () => {
    const liveRun = {
      id: "run-1",
      publicToken: "public-token",
      status: "ACTIVE" as const,
      artifact: {
        version: 1,
        headline: "Signal Desk for operators",
        promise: completedDraft.stimulus,
        ctaLabel: "I'm interested",
        disclosure: {
          title: "This is a concept test",
          body: "This product is not available yet.",
        },
      },
      launchedAt: "2026-07-15T12:00:00.000Z",
      closedAt: null,
    };
    mocks.getSelectionExperiments.mockResolvedValue([
      experiment({ status: "LOCKED", lockedAt: "2026-07-15T11:00:00.000Z" }),
    ]);
    mocks.launchSelectionExperiment.mockResolvedValue(liveRun);
    mocks.getSelectionExperimentResults.mockResolvedValue({
      runStatus: "ACTIVE",
      exposures: 0,
      ctaClicks: 0,
      disclosures: 0,
      ctaRate: null,
      sampleTarget: null,
      sampleProgress: null,
      firstEventAt: null,
      lastEventAt: null,
      dataQualityWarning: null,
    });
    const view = render(ExperimentWorkspace, { props: { jobId: "job-1", ideas: [idea] } });

    await fireEvent.click(await view.findByRole("button", { name: "Set up public test" }));
    expect(view.getByRole("dialog", { name: "Set up public test" })).toBeInTheDocument();
    expect(view.getByText(/Participants see only this offer/)).toBeInTheDocument();
    await fireEvent.click(view.getByRole("button", { name: "Publish test" }));

    await waitFor(() => expect(mocks.launchSelectionExperiment).toHaveBeenCalledWith(
      "job-1",
      "experiment-1",
      {
        headline: "Signal Desk for operators",
        promise: completedDraft.stimulus,
        ctaLabel: "IM_INTERESTED",
      },
    ));
    expect(await view.findByText("Still collecting")).toBeInTheDocument();
  });

  it("shows raw CTA observations without claiming the idea is validated", async () => {
    mocks.getSelectionExperiments.mockResolvedValue([
      experiment({
        status: "LOCKED",
        lockedAt: "2026-07-15T11:00:00.000Z",
        run: {
          id: "run-1",
          publicToken: "public-token",
          status: "ACTIVE",
          artifact: {
            version: 1,
            headline: "Signal Desk",
            promise: "Find buyer signals",
            ctaLabel: "I'm interested",
            disclosure: { title: "Concept test", body: "Not available yet." },
          },
          launchedAt: "2026-07-15T12:00:00.000Z",
          closedAt: null,
        },
      }),
    ]);
    mocks.getSelectionExperimentResults.mockResolvedValue({
      runStatus: "ACTIVE",
      exposures: 40,
      ctaClicks: 5,
      disclosures: 5,
      ctaRate: 0.125,
      sampleTarget: 100,
      sampleProgress: 0.4,
      firstEventAt: "2026-07-15T12:00:00.000Z",
      lastEventAt: "2026-07-15T13:00:00.000Z",
      dataQualityWarning: null,
    });
    const view = render(ExperimentWorkspace, { props: { jobId: "job-1", ideas: [idea] } });

    await fireEvent.click(await view.findByRole("button", { name: "View results" }));
    expect(await view.findByText("5 / 40 · 12.5%")).toBeInTheDocument();
    expect(view.getByText(/does not prove willingness to pay/)).toBeInTheDocument();
    expect(view.queryByText(/idea validated/i)).not.toBeInTheDocument();
  });

  it("records an external result with an explicit immutable owner conclusion", async () => {
    const locked = experiment({
      status: "LOCKED",
      lockedAt: "2026-07-15T11:00:00.000Z",
      method: "CUSTOMER_INTERVIEWS",
      evidenceSignal: "LANGUAGE",
    });
    mocks.getSelectionExperiments.mockResolvedValue([locked]);
    mocks.concludeSelectionExperiment.mockImplementation(async (_jobId, _experimentId, input) => ({
      id: "conclusion-1",
      experimentId: "experiment-1",
      ideaId: "idea-signal",
      ideaRevision: 3,
      outcome: input.outcome,
      evidenceSource: input.evidenceSource,
      requestFingerprint: "fingerprint",
      ownerRationale: input.ownerRationale,
      nextActionSnapshot: locked.failAction,
      snapshot: {
        schemaVersion: 1,
        experiment: {},
        precommitment: {},
        evidence: {},
        adjudication: {},
      },
      concludedByUserId: "owner-1",
      createdAt: "2026-07-16T00:00:00.000Z",
    }));
    const view = render(ExperimentWorkspace, { props: { jobId: "job-1", ideas: [idea] } });

    await fireEvent.click(await view.findByRole("button", { name: "Record external result" }));
    expect(view.getByRole("dialog", { name: "Record test conclusion" })).toBeInTheDocument();
    await fireEvent.click(view.getByRole("radio", { name: /Fail rule met/ }));
    await fireEvent.input(view.getByLabelText("Observed result", { exact: false }), {
      target: { value: "One of twelve qualified interviewees requested a follow-up." },
    });
    await fireEvent.input(view.getByLabelText("Why this outcome fits the written rule", { exact: false }), {
      target: { value: "The observed behavior stayed below the precommitted fail rule." },
    });

    await fireEvent.click(view.getByRole("button", { name: "Save conclusion" }));

    await waitFor(() => expect(mocks.concludeSelectionExperiment).toHaveBeenCalledWith(
      "job-1",
      "experiment-1",
      expect.objectContaining({
        evidenceSource: "MANUAL",
        outcome: "FAIL",
        observationSummary: "One of twelve qualified interviewees requested a follow-up.",
        ownerRationale: "The observed behavior stayed below the precommitted fail rule.",
      }),
    ));
    expect(await view.findByText("Your conclusion")).toBeInTheDocument();
    expect(view.getByText(locked.failAction)).toBeInTheDocument();
    expect(view.getByText(/does not validate the idea/i)).toBeInTheDocument();
  });

  it("submits no client-authored counts when concluding a closed hosted run", async () => {
    const hosted = experiment({
      status: "LOCKED",
      lockedAt: "2026-07-15T11:00:00.000Z",
      sampleTarget: 100,
      run: {
        id: "run-1",
        publicToken: "public-token",
        status: "CLOSED",
        artifact: {
          version: 1,
          headline: "Signal Desk",
          promise: "Find buyer signals",
          ctaLabel: "I'm interested",
          disclosure: { title: "Concept test", body: "Not available yet." },
        },
        launchedAt: "2026-07-15T12:00:00.000Z",
        closedAt: "2026-07-15T14:00:00.000Z",
      },
    });
    mocks.getSelectionExperiments.mockResolvedValue([hosted]);
    mocks.getSelectionExperimentResults.mockResolvedValue({
      runStatus: "CLOSED",
      exposures: 120,
      ctaClicks: 11,
      disclosures: 11,
      ctaRate: 11 / 120,
      sampleTarget: 100,
      sampleProgress: 1,
      firstEventAt: "2026-07-15T12:01:00.000Z",
      lastEventAt: "2026-07-15T13:59:00.000Z",
      dataQualityWarning: null,
    });
    mocks.concludeSelectionExperiment.mockResolvedValue({
      id: "conclusion-1",
      experimentId: "experiment-1",
      ideaId: "idea-signal",
      ideaRevision: 3,
      outcome: "PASS",
      evidenceSource: "HOSTED_RUN",
      requestFingerprint: "fingerprint",
      ownerRationale: "The closed run cleared the written rate and sample rules.",
      nextActionSnapshot: hosted.passAction,
      snapshot: { schemaVersion: 1, experiment: {}, precommitment: {}, evidence: {}, adjudication: {} },
      concludedByUserId: "owner-1",
      createdAt: "2026-07-16T00:00:00.000Z",
    });
    const view = render(ExperimentWorkspace, { props: { jobId: "job-1", ideas: [idea] } });

    await fireEvent.click(await view.findByRole("button", { name: "Review and record outcome" }));
    expect(await view.findByText("11 / 120 · 9.2%")).toBeInTheDocument();
    await fireEvent.click(view.getByRole("radio", { name: /Pass rule met/ }));
    await fireEvent.input(view.getByLabelText("Why this outcome fits the written rule", { exact: false }), {
      target: { value: "The closed run cleared the written rate and sample rules." },
    });
    await fireEvent.click(view.getByRole("button", { name: "Save conclusion" }));

    await waitFor(() => expect(mocks.concludeSelectionExperiment).toHaveBeenCalledOnce());
    const submitted = mocks.concludeSelectionExperiment.mock.calls[0][2];
    expect(submitted).toEqual({
      evidenceSource: "HOSTED_RUN",
      outcome: "PASS",
      ownerRationale: "The closed run cleared the written rate and sample rules.",
      limitations: [],
    });
    expect(submitted).not.toHaveProperty("exposures");
    expect(submitted).not.toHaveProperty("ctaClicks");
    expect(view.queryByText(/idea validated/i)).not.toBeInTheDocument();
  });

  it("switches candidates immediately with no confirmation when the draft is clean", async () => {
    mocks.getSelectionExperiments.mockResolvedValue([]);
    const view = render(ExperimentWorkspace, { props: { jobId: "job-1", ideas: [idea, idea2] } });

    await fireEvent.click(await view.findByRole("button", { name: "Plan a test" }));
    const select = view.getByLabelText("Candidate", { exact: false }) as HTMLSelectElement;
    expect(view.getByLabelText("One atomic assumption that must be true", { exact: false })).toHaveValue(
      idea.critic_concern,
    );

    await fireEvent.change(select, { target: { value: "idea-ledger" } });

    expect(select.value).toBe("idea-ledger");
    expect(view.getByLabelText("One atomic assumption that must be true", { exact: false })).toHaveValue(
      idea2.critic_concern,
    );
    expect(view.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("holds the draft and shows an inline confirmation when switching a dirty draft", async () => {
    mocks.getSelectionExperiments.mockResolvedValue([]);
    const view = render(ExperimentWorkspace, { props: { jobId: "job-1", ideas: [idea, idea2] } });

    await fireEvent.click(await view.findByRole("button", { name: "Plan a test" }));
    const assumptionField = view.getByLabelText("One atomic assumption that must be true", { exact: false });
    await fireEvent.input(assumptionField, { target: { value: "A hand-typed unsaved assumption." } });

    const select = view.getByLabelText("Candidate", { exact: false }) as HTMLSelectElement;
    await fireEvent.change(select, { target: { value: "idea-ledger" } });

    expect(select.value).toBe("idea-signal");
    expect(assumptionField).toHaveValue("A hand-typed unsaved assumption.");
    expect(
      await view.findByText(/Switching to Ledger Watch for bookkeepers replaces every field below/),
    ).toBeInTheDocument();
  });

  it("confirming the switch discards the draft and applies the new candidate's starting values", async () => {
    mocks.getSelectionExperiments.mockResolvedValue([]);
    const view = render(ExperimentWorkspace, { props: { jobId: "job-1", ideas: [idea, idea2] } });

    await fireEvent.click(await view.findByRole("button", { name: "Plan a test" }));
    const assumptionField = view.getByLabelText("One atomic assumption that must be true", { exact: false });
    await fireEvent.input(assumptionField, { target: { value: "A hand-typed unsaved assumption." } });
    const select = view.getByLabelText("Candidate", { exact: false }) as HTMLSelectElement;
    await fireEvent.change(select, { target: { value: "idea-ledger" } });

    await fireEvent.click(await view.findByRole("button", { name: "Discard draft and switch" }));

    expect(select.value).toBe("idea-ledger");
    expect(assumptionField).toHaveValue(idea2.critic_concern);
    expect(view.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("cancelling the switch keeps the original draft and select value", async () => {
    mocks.getSelectionExperiments.mockResolvedValue([]);
    const view = render(ExperimentWorkspace, { props: { jobId: "job-1", ideas: [idea, idea2] } });

    await fireEvent.click(await view.findByRole("button", { name: "Plan a test" }));
    const assumptionField = view.getByLabelText("One atomic assumption that must be true", { exact: false });
    await fireEvent.input(assumptionField, { target: { value: "A hand-typed unsaved assumption." } });
    const select = view.getByLabelText("Candidate", { exact: false }) as HTMLSelectElement;
    await fireEvent.change(select, { target: { value: "idea-ledger" } });

    await fireEvent.click(await view.findByRole("button", { name: "Keep editing" }));

    expect(select.value).toBe("idea-signal");
    expect(assumptionField).toHaveValue("A hand-typed unsaved assumption.");
    expect(view.queryByRole("alert")).not.toBeInTheDocument();
  });
});
