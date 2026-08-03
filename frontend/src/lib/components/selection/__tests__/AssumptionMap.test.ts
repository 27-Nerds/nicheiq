import { cleanup, fireEvent, render, waitFor, within } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import AssumptionMap from "../AssumptionMap.svelte";
import type { SelectionAssumption } from "$lib/types/selectionAssumption";
import type { SelectionChallenge } from "$lib/types/selectionChallenge";
import type { SolutionPreview } from "$lib/types/job";
import type { SelectionAssumptionPrefill } from "$lib/types/selectionCopilot";

const apiMocks = vi.hoisted(() => ({
  ApiError: class ApiError extends Error {
    constructor(message: string, public status: number) {
      super(message);
    }
  },
  getSelectionAssumptions: vi.fn(),
  getSelectionChallenges: vi.fn(),
  createSelectionAssumption: vi.fn(),
  updateSelectionAssumption: vi.fn(),
}));

vi.mock("$lib/api", () => apiMocks);

const signal: SolutionPreview = {
  idea_id: "idea-signal",
  idea_revision: 3,
  solution_name: "Signal Desk",
  description: "Signal Desk description",
  value_proposition: "Find recurring buying signals",
};

function assumption(overrides: Partial<SelectionAssumption> = {}): SelectionAssumption {
  return {
    id: "assumption-1",
    jobId: "job-1",
    ideaId: "idea-signal",
    ideaRevision: 3,
    lens: "demand",
    statement: "Qualified buyers will make a concrete payment commitment for this outcome.",
    impactIfFalse: "We would stop this candidate before paid validation.",
    falsificationQuestion: "Will fewer than three of ten qualified buyers make a deposit?",
    impact: "DECISIVE",
    ownerState: "OPEN",
    version: 4,
    originChallengeId: "challenge-1",
    originQuestionId: "buyer_will_pay",
    createdByUserId: "user-1",
    createdAt: "2026-07-16T00:00:00.000Z",
    updatedAt: "2026-07-16T01:00:00.000Z",
    stale: false,
    direction: "MIXED",
    evidenceClass: "PROXY",
    experiments: [{ id: "experiment-1", status: "LOCKED", outcome: "AMBIGUOUS" }],
    ...overrides,
  };
}

function challenge(): SelectionChallenge {
  return {
    id: "challenge-1",
    version: 1,
    inputFingerprint: "f".repeat(64),
    ideaId: "idea-signal",
    ideaRevision: 3,
    ideaTitle: "Signal Desk",
    lens: "demand",
    overall: "insufficient_evidence",
    ideaSnapshot: {},
    subjectSnapshot: [],
    evidenceSnapshot: [],
    questions: [{
      questionId: "buyer_will_pay",
      consensus: "insufficient",
      skeptic: {
        questionId: "buyer_will_pay",
        position: "insufficient",
        summary: "Payment commitment is not established.",
        subjectKeys: [],
        evidenceKeys: [],
        evidenceClass: "inference",
      },
      auditor: {
        questionId: "buyer_will_pay",
        position: "insufficient",
        summary: "No payment behavior was captured.",
        subjectKeys: [],
        evidenceKeys: [],
        evidenceClass: "inference",
      },
    }],
    skepticModel: "skeptic-test",
    auditorModel: "auditor-test",
    promptVersion: 1,
    createdAt: "2026-07-16T00:00:00.000Z",
  };
}

function analystPrefill(
  overrides: Partial<SelectionAssumptionPrefill> = {},
): SelectionAssumptionPrefill {
  return {
    requestId: "copilot-assumption-1",
    ideaId: "idea-signal",
    ideaRevision: 3,
    lens: "demand",
    origin: { challengeId: "challenge-1", questionId: "buyer_will_pay" },
    values: {
      statement: "Qualified buyers will make a concrete payment commitment.",
      impactIfFalse: "Stop this candidate before paid validation.",
      falsificationQuestion: "Will three of ten qualified buyers make a deposit?",
    },
    grounding: {
      statement: [{ ref: "Q1", kind: "challenge_question", label: "Demand evidence check · buyer will pay" }],
      impactIfFalse: [{ ref: "R1", kind: "candidate", label: "Candidate · Signal Desk" }],
      falsificationQuestion: [{ ref: "O1", kind: "owner_evidence", label: "Owner evidence · Interview note" }],
    },
    rationale: "Turn the current demand gap into a falsifiable owner-reviewed assumption.",
    caveats: ["Payment behavior has not been observed yet."],
    ...overrides,
  };
}

describe("AssumptionMap", () => {
  afterEach(cleanup);

  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.getSelectionAssumptions.mockResolvedValue({ assumptions: [] });
    apiMocks.getSelectionChallenges.mockResolvedValue({ challenges: [], stale: [] });
  });

  it("keeps owner impact, derived evidence, linked status, and older revisions visibly separate", async () => {
    apiMocks.getSelectionAssumptions.mockResolvedValue({
      assumptions: [
        assumption(),
        assumption({
          id: "assumption-old",
          ideaRevision: 2,
          statement: "The previous audience could be reached through communities.",
          impact: "HIGH",
          stale: true,
          direction: "SUPPORTING",
          evidenceClass: "OBSERVED",
          experiments: [],
        }),
      ],
    });
    const view = render(AssumptionMap, { props: { jobId: "job-1", ideas: [signal] } });

    await waitFor(() => expect(view.getByText("Mixed direction")).toBeInTheDocument());
    expect(view.getByText("Proxy evidence")).toBeInTheDocument();
    expect(view.getByText("Result ambiguous")).toBeInTheDocument();
    expect(view.getByText("Decision-changing impact")).toBeInTheDocument();
    expect(view.getByText("Older revision · rev 2")).toBeInTheDocument();
    expect(view.getByText("Observed evidence")).toBeInTheDocument();
    expect(view.container).not.toHaveTextContent(/\d+\s*\/\s*100|assumption score/i);
    expect(view.getAllByRole("button", { name: "Edit" })).toHaveLength(1);
  });

  it("does not duplicate a risk-check question in the saved-question list", async () => {
    apiMocks.getSelectionChallenges.mockResolvedValue({ challenges: [challenge()], stale: [] });
    const view = render(AssumptionMap, { props: { jobId: "job-1", ideas: [signal] } });

    await waitFor(() => expect(view.getByText("No questions saved yet.")).toBeInTheDocument());
    expect(view.queryByRole("button", { name: /Add to things to prove/ })).not.toBeInTheDocument();
    expect(view.getByRole("button", { name: /Add a question to resolve/ })).toBeInTheDocument();
  });

  it("opens an analyst assumption draft without saving and refuses to replace dirty owner input", async () => {
    apiMocks.getSelectionChallenges.mockResolvedValue({ challenges: [challenge()], stale: [] });
    const firstPrefill = analystPrefill();
    const view = render(AssumptionMap, {
      props: { jobId: "job-1", ideas: [signal], prefill: firstPrefill },
    });

    const dialog = await view.findByRole("dialog", { name: "Save a question to resolve" });
    expect(within(dialog).getByDisplayValue(firstPrefill.values.statement!)).toBeInTheDocument();
    expect(within(dialog).getByText("Suggested draft · not saved")).toBeInTheDocument();
    expect(within(dialog).getByText("Candidate · Signal Desk")).toBeInTheDocument();
    expect(within(dialog).getByText("Owner evidence · Interview note")).toBeInTheDocument();
    expect(within(dialog).getByText(/You still choose how much this matters/)).toBeInTheDocument();
    expect(within(dialog).getByText(/Payment behavior has not been observed yet/)).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Save question" })).not.toBeDisabled();
    expect(within(dialog).getAllByRole("radio").every((radio) => !(radio as HTMLInputElement).checked)).toBe(true);
    expect(apiMocks.createSelectionAssumption).not.toHaveBeenCalled();

    await fireEvent.input(within(dialog).getByLabelText(/What must be true\?/), {
      target: { value: "My unsaved owner wording" },
    });
    await view.rerender({
      jobId: "job-1",
      ideas: [signal],
      prefill: {
        ...firstPrefill,
        requestId: "copilot-assumption-2",
        values: { ...firstPrefill.values, statement: "A replacement analyst draft" },
      },
    });

    expect(await view.findByRole("alert")).toHaveTextContent("unsaved changes");
    expect(within(dialog).getByDisplayValue("My unsaved owner wording")).toBeInTheDocument();
    expect(apiMocks.createSelectionAssumption).not.toHaveBeenCalled();
  });

  it("replaces an untouched analyst draft when a second prefill arrives", async () => {
    apiMocks.getSelectionChallenges.mockResolvedValue({ challenges: [challenge()], stale: [] });
    const firstPrefill = analystPrefill();
    const view = render(AssumptionMap, {
      props: { jobId: "job-1", ideas: [signal], prefill: firstPrefill },
    });

    const dialog = await view.findByRole("dialog", { name: "Save a question to resolve" });
    expect(within(dialog).getByDisplayValue(firstPrefill.values.statement!)).toBeInTheDocument();

    await view.rerender({
      jobId: "job-1",
      ideas: [signal],
      prefill: {
        ...firstPrefill,
        requestId: "copilot-assumption-2",
        values: { ...firstPrefill.values, statement: "A replacement analyst draft" },
      },
    });

    expect(await within(dialog).findByDisplayValue("A replacement analyst draft")).toBeInTheDocument();
    expect(within(dialog).queryByDisplayValue(firstPrefill.values.statement!)).not.toBeInTheDocument();
    expect(view.queryByText(/unsaved changes/)).not.toBeInTheDocument();
    expect(apiMocks.createSelectionAssumption).not.toHaveBeenCalled();
  });

  it("saves an analyst draft only after the owner chooses impact", async () => {
    apiMocks.getSelectionChallenges.mockResolvedValue({ challenges: [challenge()], stale: [] });
    apiMocks.createSelectionAssumption.mockResolvedValue({ assumption: assumption(), cached: false });
    const draft = analystPrefill();
    const view = render(AssumptionMap, {
      props: { jobId: "job-1", ideas: [signal], prefill: draft },
    });

    const dialog = await view.findByRole("dialog", { name: "Save a question to resolve" });
    expect(apiMocks.createSelectionAssumption).not.toHaveBeenCalled();

    // The button stays enabled even without a chosen impact: clicking it
    // while invalid reveals the field error instead of silently saving.
    const trackButton = within(dialog).getByRole("button", { name: "Save question" });
    expect(trackButton).not.toBeDisabled();
    await fireEvent.click(trackButton);
    expect(apiMocks.createSelectionAssumption).not.toHaveBeenCalled();
    expect(within(dialog).getByText("Choose how much this would change your decision.")).toBeInTheDocument();

    await fireEvent.click(within(dialog).getByRole("radio", { name: /Decision-changing/ }));
    await fireEvent.click(within(dialog).getByRole("button", { name: "Save question" }));

    await waitFor(() => expect(apiMocks.createSelectionAssumption).toHaveBeenCalledWith("job-1", {
      ideaId: "idea-signal",
      ideaRevision: 3,
      lens: "demand",
      statement: draft.values.statement,
      impactIfFalse: draft.values.impactIfFalse,
      falsificationQuestion: draft.values.falsificationQuestion,
      impact: "DECISIVE",
      originChallengeId: "challenge-1",
      originQuestionId: "buyer_will_pay",
    }));
  });

  it("reconciles the authoritative questions and parent decision state after saving", async () => {
    const saved = assumption({ experiments: [] });
    apiMocks.getSelectionAssumptions
      .mockResolvedValueOnce({ assumptions: [] })
      .mockResolvedValue({ assumptions: [saved] });
    apiMocks.getSelectionChallenges.mockResolvedValue({ challenges: [challenge()], stale: [] });
    apiMocks.createSelectionAssumption.mockResolvedValue({ assumption: saved, cached: false });
    const onChanged = vi.fn().mockResolvedValue(undefined);
    const view = render(AssumptionMap, {
      props: {
        jobId: "job-1",
        ideas: [signal],
        prefill: analystPrefill(),
        onChanged,
      },
    });

    const dialog = await view.findByRole("dialog", { name: "Save a question to resolve" });
    await fireEvent.click(within(dialog).getByRole("radio", { name: /Decision-changing/ }));
    await fireEvent.click(within(dialog).getByRole("button", { name: "Save question" }));

    await waitFor(() => expect(apiMocks.getSelectionAssumptions).toHaveBeenCalledTimes(2));
    expect(apiMocks.getSelectionChallenges).toHaveBeenCalledTimes(2);
    expect(onChanged).toHaveBeenCalledTimes(1);
    expect(await view.findByText(saved.statement)).toBeInTheDocument();
  });

  it("shows a saved-but-stale warning and lets the owner retry reconciliation", async () => {
    const saved = assumption({ experiments: [] });
    apiMocks.getSelectionAssumptions
      .mockResolvedValueOnce({ assumptions: [] })
      .mockRejectedValueOnce(new Error("network unavailable"))
      .mockResolvedValue({ assumptions: [saved] });
    apiMocks.getSelectionChallenges.mockResolvedValue({ challenges: [challenge()], stale: [] });
    apiMocks.createSelectionAssumption.mockResolvedValue({ assumption: saved, cached: false });
    const onChanged = vi.fn().mockResolvedValue(undefined);
    const onTestUnknown = vi.fn();
    const view = render(AssumptionMap, {
      props: {
        jobId: "job-1",
        ideas: [signal],
        prefill: analystPrefill(),
        onChanged,
        onTestUnknown,
      },
    });

    const dialog = await view.findByRole("dialog", { name: "Save a question to resolve" });
    await fireEvent.click(within(dialog).getByRole("radio", { name: /Decision-changing/ }));
    await fireEvent.click(within(dialog).getByRole("button", { name: "Save question" }));

    const warning = await view.findByRole("alert");
    expect(warning).toHaveTextContent("question was saved");
    expect(onChanged).not.toHaveBeenCalled();
    expect(view.getByRole("button", { name: /Add a question to resolve/ })).toBeDisabled();
    expect(view.getByRole("button", { name: "Edit" })).toBeDisabled();
    expect(view.getByRole("button", { name: "Draft test" })).toBeDisabled();
    await fireEvent.click(view.getByRole("button", { name: "Draft test" }));
    expect(onTestUnknown).not.toHaveBeenCalled();
    await fireEvent.click(within(warning).getByRole("button", { name: "Reload current state" }));

    await waitFor(() => expect(apiMocks.getSelectionAssumptions).toHaveBeenCalledTimes(3));
    expect(onChanged).toHaveBeenCalledTimes(1);
    expect(view.queryByText(/current decision state could not be refreshed/i)).not.toBeInTheDocument();
    expect(await view.findByText(saved.statement)).toBeInTheDocument();
    expect(view.getByRole("button", { name: /Add a question to resolve/ })).toBeEnabled();
    expect(view.getByRole("button", { name: "Edit" })).toBeEnabled();
    expect(view.getByRole("button", { name: "Draft test" })).toBeEnabled();
  });

  it("rejects an analyst edit prepared against an older assumption version", async () => {
    apiMocks.getSelectionAssumptions.mockResolvedValue({ assumptions: [assumption()] });
    const view = render(AssumptionMap, {
      props: {
        jobId: "job-1",
        ideas: [signal],
        prefill: {
          ...analystPrefill({ requestId: "copilot-assumption-stale", origin: undefined }),
          record: { id: "assumption-1", version: 3 },
          values: { statement: "Updated analyst wording for the current assumption." },
          grounding: {
            statement: [{ ref: "A1", kind: "assumption", label: "Current assumption · Qualified buyers will pay" }],
          },
        },
      },
    });

    expect(await view.findByRole("alert")).toHaveTextContent("changed after the draft was prepared");
    expect(view.queryByRole("dialog", { name: "Edit question to resolve" })).not.toBeInTheDocument();
    expect(apiMocks.updateSelectionAssumption).not.toHaveBeenCalled();
  });

  it("updates only owner fields with an exact revision and expected version", async () => {
    const current = assumption({ experiments: [] });
    apiMocks.getSelectionAssumptions.mockResolvedValue({ assumptions: [current] });
    apiMocks.updateSelectionAssumption.mockResolvedValue({
      assumption: { ...current, version: 5, ownerState: "ACCEPTED_RISK" },
    });
    const view = render(AssumptionMap, { props: { jobId: "job-1", ideas: [signal] } });

    await waitFor(() => expect(view.getByRole("button", { name: "Edit" })).toBeInTheDocument());
    await fireEvent.click(view.getByRole("button", { name: "Edit" }));
    const dialog = view.getByRole("dialog", { name: "Edit question to resolve" });
    await fireEvent.change(within(dialog).getByLabelText(/Status/), { target: { value: "ACCEPTED_RISK" } });
    await fireEvent.click(within(dialog).getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(apiMocks.updateSelectionAssumption).toHaveBeenCalledWith(
      "job-1",
      "assumption-1",
      expect.objectContaining({
        expectedVersion: 4,
        ideaId: "idea-signal",
        ideaRevision: 3,
        ownerState: "ACCEPTED_RISK",
      }),
    ));
    const patch = apiMocks.updateSelectionAssumption.mock.calls[0][2];
    expect(patch).not.toHaveProperty("direction");
    expect(patch).not.toHaveProperty("evidenceClass");
  });

  it("prefills a linked test with the durable assumption id after owner action", async () => {
    apiMocks.getSelectionAssumptions.mockResolvedValue({
      assumptions: [assumption({ experiments: [], direction: "UNKNOWN", evidenceClass: "NONE" })],
    });
    const onTestUnknown = vi.fn();
    const view = render(AssumptionMap, {
      props: { jobId: "job-1", ideas: [signal], onTestUnknown },
    });

    await waitFor(() => expect(view.getByRole("button", { name: "Draft test" })).toBeInTheDocument());
    await fireEvent.click(view.getByRole("button", { name: "Draft test" }));

    expect(onTestUnknown).toHaveBeenCalledWith(expect.objectContaining({
      ideaId: "idea-signal",
      ideaRevision: 3,
      assumptionId: "assumption-1",
      originChallengeId: "challenge-1",
      originQuestionId: "buyer_will_pay",
    }));
  });

  it("routes the editor footer Cancel through the dirty gate", async () => {
    const view = render(AssumptionMap, { props: { jobId: "job-1", ideas: [signal] } });

    await waitFor(() => expect(view.getByRole("button", { name: /Add a question to resolve/ })).toBeEnabled());
    await fireEvent.click(view.getByRole("button", { name: /Add a question to resolve/ }));
    const dialog = view.getByRole("dialog", { name: "Save a question to resolve" });
    await fireEvent.input(within(dialog).getByLabelText(/What must be true\?/), {
      target: { value: "A hand-typed unsaved belief." },
    });

    await fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(view.getByRole("dialog", { name: "Save a question to resolve" })).toBeInTheDocument();
    expect(view.getByText("You have unsaved changes. Close again to discard them.")).toBeInTheDocument();

    await fireEvent.click(view.getByRole("button", { name: "Discard changes" }));
    await waitFor(() =>
      expect(view.queryByRole("dialog", { name: "Save a question to resolve" })).not.toBeInTheDocument(),
    );
  });

  it("closes a clean editor from the footer Cancel on the first click", async () => {
    const view = render(AssumptionMap, { props: { jobId: "job-1", ideas: [signal] } });

    await waitFor(() => expect(view.getByRole("button", { name: /Add a question to resolve/ })).toBeEnabled());
    await fireEvent.click(view.getByRole("button", { name: /Add a question to resolve/ }));
    await fireEvent.click(view.getByRole("button", { name: "Cancel" }));

    await waitFor(() =>
      expect(view.queryByRole("dialog", { name: "Save a question to resolve" })).not.toBeInTheDocument(),
    );
    expect(
      view.queryByText("You have unsaved changes. Close again to discard them."),
    ).not.toBeInTheDocument();
  });

  it("explains and focuses the first missing field on a failed save", async () => {
    const view = render(AssumptionMap, { props: { jobId: "job-1", ideas: [signal] } });

    await waitFor(() => expect(view.getByRole("button", { name: /Add a question to resolve/ })).toBeEnabled());
    await fireEvent.click(view.getByRole("button", { name: /Add a question to resolve/ }));
    const dialog = view.getByRole("dialog", { name: "Save a question to resolve" });
    await fireEvent.click(within(dialog).getByRole("button", { name: "Save question" }));

    expect(within(dialog).getByText("Describe what must be true in at least 3 characters.")).toBeInTheDocument();
    expect(within(dialog).getByText("Say what you would change, stop, or investigate if this is false.")).toBeInTheDocument();
    expect(within(dialog).getByText("Write the observable result that would prove this wrong.")).toBeInTheDocument();
    await waitFor(() => expect(document.activeElement?.id).toBe("assumption-statement"));
    expect(apiMocks.createSelectionAssumption).not.toHaveBeenCalled();
  });

  it("stops on a stale write and reloads instead of overwriting a newer version", async () => {
    const current = assumption({ experiments: [] });
    apiMocks.getSelectionAssumptions.mockResolvedValue({ assumptions: [current] });
    apiMocks.updateSelectionAssumption.mockRejectedValue(new apiMocks.ApiError("Version conflict", 409));
    const view = render(AssumptionMap, { props: { jobId: "job-1", ideas: [signal] } });

    await waitFor(() => expect(view.getByRole("button", { name: "Edit" })).toBeInTheDocument());
    await fireEvent.click(view.getByRole("button", { name: "Edit" }));
    const dialog = view.getByRole("dialog", { name: "Edit question to resolve" });
    await fireEvent.change(within(dialog).getByLabelText(/Status/), { target: { value: "ACCEPTED_RISK" } });
    await fireEvent.click(within(dialog).getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(within(dialog).getByRole("button", { name: "Reload map" })).toBeInTheDocument());
    expect(within(dialog).getByRole("alert")).toHaveTextContent("changed or its idea revision is no longer current");
    await fireEvent.click(within(dialog).getByRole("button", { name: "Reload map" }));
    await waitFor(() => expect(apiMocks.getSelectionAssumptions).toHaveBeenCalledTimes(2));
    expect(view.queryByRole("dialog", { name: "Edit question to resolve" })).not.toBeInTheDocument();
  });
});
