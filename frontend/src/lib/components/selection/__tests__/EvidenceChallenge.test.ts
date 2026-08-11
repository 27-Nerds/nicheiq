import { cleanup, fireEvent, render, waitFor, within } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import EvidenceChallenge from "../EvidenceChallenge.svelte";
import { discardOwnerEvidenceDraft } from "../OwnerEvidenceLedger.svelte";
import type { SelectionChallenge } from "$lib/types/selectionChallenge";
import type { SolutionPreview } from "$lib/types/job";

const apiMocks = vi.hoisted(() => ({
  getSelectionChallenges: vi.fn(),
  runSelectionChallenge: vi.fn(),
  getSelectionOwnerEvidence: vi.fn(),
  createSelectionOwnerEvidence: vi.fn(),
  retractSelectionOwnerEvidence: vi.fn(),
}));

vi.mock("$lib/api", () => apiMocks);

const idea: SolutionPreview = {
  idea_id: "idea-signal-desk",
  idea_revision: 3,
  solution_name: "Signal Desk",
  description: "Find recurring demand signals.",
  value_proposition: "Trace each opportunity to customer language.",
};

const challenge: SelectionChallenge = {
  id: "challenge-1",
  version: 1,
  inputFingerprint: "f".repeat(64),
  ideaId: "idea-signal-desk",
  ideaRevision: 3,
  ideaTitle: "Signal Desk",
  lens: "demand",
  overall: "disputed",
  ideaSnapshot: { solution_name: "Signal Desk" },
  subjectSnapshot: [{ key: "I1", field: "value_proposition", value: idea.value_proposition }],
  evidenceSnapshot: [{
    key: "S1",
    kind: "customer_quote",
    title: "Customer interview",
    excerpt: "I spend every Friday copying the same demand notes.",
    url: "https://example.com/interview",
    capturedAt: "2026-07-16T00:00:00.000Z",
    provenance: { assetType: "DISCOVERY_DATA", jsonPointer: "/solution_ideas/0/source_pain" },
  }],
  questions: [
    {
      questionId: "pain_is_observed",
      consensus: "disputed",
      skeptic: {
        questionId: "pain_is_observed",
        position: "contradicts",
        summary: "The quote shows a task, but not a costly recurring problem.",
        subjectKeys: ["I1"],
        evidenceKeys: ["S1"],
        evidenceClass: "observed",
      },
      auditor: {
        questionId: "pain_is_observed",
        position: "supports",
        summary: "The quote directly reports repeated manual work.",
        subjectKeys: ["I1"],
        evidenceKeys: ["S1"],
        evidenceClass: "observed",
      },
    },
    {
      questionId: "urgency_is_behavioral",
      consensus: "insufficient",
      skeptic: {
        questionId: "urgency_is_behavioral",
        position: "insufficient",
        summary: "No workaround spend or switching behavior is captured.",
        subjectKeys: ["I1"],
        evidenceKeys: [],
        evidenceClass: "inference",
      },
      auditor: {
        questionId: "urgency_is_behavioral",
        position: "insufficient",
        summary: "The research does not establish urgency.",
        subjectKeys: ["I1"],
        evidenceKeys: [],
        evidenceClass: "inference",
      },
    },
    {
      questionId: "buyer_will_pay",
      consensus: "insufficient",
      skeptic: {
        questionId: "buyer_will_pay",
        position: "insufficient",
        summary: "No payment signal is captured.",
        subjectKeys: ["I1"],
        evidenceKeys: [],
        evidenceClass: "inference",
      },
      auditor: {
        questionId: "buyer_will_pay",
        position: "insufficient",
        summary: "No price or commitment evidence is present.",
        subjectKeys: ["I1"],
        evidenceKeys: [],
        evidenceClass: "inference",
      },
    },
  ],
  skepticModel: "model-skeptic",
  auditorModel: "model-auditor",
  promptVersion: 1,
  createdAt: "2026-07-16T00:00:00.000Z",
};

const experimentSources: SelectionChallenge["evidenceSnapshot"] = [
  {
    key: "E1",
    kind: "experiment_result",
    title: "Hosted CTA test",
    excerpt: "18 of 120 visitors requested early access.",
    url: null,
    capturedAt: "2026-07-16T00:00:00.000Z",
    provenance: {
      assetType: "EXPERIMENT_RESULT",
      experimentId: "experiment-hosted",
      conclusionId: "conclusion-hosted",
      originChallengeId: challenge.id,
      evidenceClass: "observed",
      sourceType: "FIRST_PARTY",
      adapterKey: "hosted-cta",
      precommitment: {
        primaryMetric: "Early-access requests",
        passThreshold: "At least 12 requests",
        failThreshold: "Fewer than 6 requests",
        measurementWindow: "7 days",
        sampleTarget: 100,
      },
      observation: {
        observedThrough: "2026-07-16T00:00:00.000Z",
        observationSummary: "The hosted test cleared its precommitted request threshold.",
        observedMetric: "18 requests",
        metrics: [{
          key: "requests",
          label: "Requests",
          valueType: "count",
          value: 18,
          isPrimary: true,
        }],
        sample: { observed: 120, target: 100, unit: "visitors" },
        limitations: ["One acquisition channel"],
      },
    },
  },
  {
    key: "E2",
    kind: "experiment_result",
    title: "External interview test",
    excerpt: "The owner recorded 4 commitments across 8 interviews.",
    url: null,
    capturedAt: "2026-07-15T00:00:00.000Z",
    provenance: {
      assetType: "EXPERIMENT_RESULT",
      experimentId: "experiment-manual",
      conclusionId: "conclusion-manual",
      originChallengeId: challenge.id,
      evidenceClass: "proxy",
      sourceType: "MANUAL",
      adapterKey: "manual",
      precommitment: {
        primaryMetric: "Commitments",
        passThreshold: "At least 5 commitments",
        failThreshold: "Fewer than 2 commitments",
        measurementWindow: "14 days",
        sampleTarget: 10,
      },
      observation: {
        observedThrough: null,
        observationSummary: "The owner recorded an external interview result.",
        observedMetric: "4 commitments",
        metrics: [],
        sample: { observed: 8, target: 10, unit: "interviews" },
        limitations: ["Owner-recorded result"],
      },
    },
  },
];

describe("EvidenceChallenge", () => {
  afterEach(cleanup);

  beforeEach(() => {
    discardOwnerEvidenceDraft();
    apiMocks.getSelectionChallenges.mockReset().mockResolvedValue({ challenges: [], stale: [] });
    apiMocks.runSelectionChallenge.mockReset().mockResolvedValue({ challenge, cached: false });
    apiMocks.getSelectionOwnerEvidence.mockReset().mockResolvedValue({ evidence: [], editable: true });
    apiMocks.createSelectionOwnerEvidence.mockReset();
    apiMocks.retractSelectionOwnerEvidence.mockReset();
  });

  it("runs against the exact idea revision and preserves disagreement with provenance", async () => {
    const view = render(EvidenceChallenge, {
      props: { jobId: "job-123", ideas: [idea] },
    });

    await waitFor(() => expect(apiMocks.getSelectionChallenges).toHaveBeenCalledWith("job-123"));
    expect(view.getByText(/Two review perspectives reread the evidence saved for this idea/)).toBeInTheDocument();
    expect(view.getByText(/They do not search for new sources/)).toBeInTheDocument();
    await fireEvent.click(await view.findByRole("button", { name: "Check demand" }));

    await waitFor(() => expect(apiMocks.runSelectionChallenge).toHaveBeenCalledWith("job-123", {
      ideaId: "idea-signal-desk",
      ideaRevision: 3,
      lens: "demand",
    }));
    expect(view.getByText("Review perspectives disagree")).toBeInTheDocument();
    expect(view.getByText(/read the same evidence differently/)).toBeInTheDocument();
    for (const heading of ["Supports", "Raises concern", "Still unknown", "Impact", "Next action"]) {
      expect(view.getAllByRole("heading", { name: heading }).length).toBeGreaterThan(0);
    }
    expect(view.getAllByText("Challenge perspective").length).toBeGreaterThan(0);
    expect(view.getAllByText("Evidence perspective").length).toBeGreaterThan(0);
    await fireEvent.click(view.getByText("1 cited source"));
    expect(view.getByText("Observed")).toBeInTheDocument();
    expect(view.getByRole("link", { name: "Open source for Customer interview (opens in new tab)" })).toHaveAttribute(
      "href",
      "https://example.com/interview",
    );
    expect(view.getByText(/Uses saved evidence only/)).toBeInTheDocument();
  });

  it("renders structured legacy excerpts as readable cited facts", async () => {
    const legacyChallenge: SelectionChallenge = {
      ...challenge,
      evidenceSnapshot: [{
        ...challenge.evidenceSnapshot[0],
        kind: "competitor_fact",
        title: "Liquipedia",
        excerpt: '{"focus":"esports match tracking","pricing":"free","gap":"tournament data only"}',
        url: null,
      }],
    };
    apiMocks.getSelectionChallenges.mockResolvedValue({ challenges: [legacyChallenge], stale: [] });
    const view = render(EvidenceChallenge, {
      props: { jobId: "job-123", ideas: [idea] },
    });

    await waitFor(() => expect(view.getByText("Review perspectives disagree")).toBeInTheDocument());
    await fireEvent.click(view.getByText("1 cited source"));
    expect(view.getByText("Focus: esports match tracking · Pricing: free · Gap: tournament data only")).toBeInTheDocument();
    expect(view.queryByText(legacyChallenge.evidenceSnapshot[0].excerpt)).not.toBeInTheDocument();
  });

  it("keeps malformed structured excerpts escaped behind a disclosure", async () => {
    const malformedExcerpt = '{"focus":"esports match tracking",broken}';
    const malformedChallenge: SelectionChallenge = {
      ...challenge,
      evidenceSnapshot: [{
        ...challenge.evidenceSnapshot[0],
        kind: "competitor_fact",
        title: "Malformed legacy source",
        excerpt: malformedExcerpt,
        url: null,
      }],
    };
    apiMocks.getSelectionChallenges.mockResolvedValue({ challenges: [malformedChallenge], stale: [] });

    const view = render(EvidenceChallenge, {
      props: { jobId: "job-123", ideas: [idea] },
    });

    await waitFor(() => expect(view.getByText("Review perspectives disagree")).toBeInTheDocument());
    await fireEvent.click(view.getByText("1 cited source"));
    expect(view.getByText("This captured source excerpt could not be formatted.")).toBeInTheDocument();

    await fireEvent.click(view.getByText("View captured text"));
    expect(view.getByText(malformedExcerpt)).toBeInTheDocument();
  });

  it("wires cited sources, captured text, and run details to tracked disclosure bodies", async () => {
    const malformedChallenge: SelectionChallenge = {
      ...challenge,
      evidenceSnapshot: [{
        ...challenge.evidenceSnapshot[0],
        kind: "competitor_fact",
        excerpt: '{"focus":"esports match tracking",broken}',
      }],
    };
    apiMocks.getSelectionChallenges.mockResolvedValue({ challenges: [malformedChallenge], stale: [] });
    const view = render(EvidenceChallenge, {
      props: { jobId: "job-123", ideas: [idea] },
    });

    await waitFor(() => expect(view.getByText("Review perspectives disagree")).toBeInTheDocument());

    const citedSummary = view.getByText("1 cited source").closest("summary");
    expect(citedSummary).toHaveAttribute("aria-expanded", "false");
    const citedBodyId = citedSummary?.getAttribute("aria-controls");
    expect(citedBodyId).toBeTruthy();
    expect(view.container.querySelector(`#${citedBodyId}`)).toBeInTheDocument();
    const citedDetails = citedSummary!.closest("details")!;
    citedDetails.open = true;
    await fireEvent(citedDetails, new Event("toggle"));
    expect(citedSummary).toHaveAttribute("aria-expanded", "true");

    const capturedSummary = view.getByText("View captured text").closest("summary");
    expect(capturedSummary).toHaveAttribute("aria-expanded", "false");
    const capturedBodyId = capturedSummary?.getAttribute("aria-controls");
    expect(capturedBodyId).toBeTruthy();
    expect(view.container.querySelector(`#${capturedBodyId}`)?.tagName).toBe("PRE");
    const capturedDetails = capturedSummary!.closest("details")!;
    capturedDetails.open = true;
    await fireEvent(capturedDetails, new Event("toggle"));
    expect(capturedSummary).toHaveAttribute("aria-expanded", "true");

    const runSummary = view.getByText("Run details").closest("summary");
    expect(runSummary).toHaveAttribute("aria-expanded", "false");
    const runBodyId = runSummary?.getAttribute("aria-controls");
    expect(runBodyId).toBeTruthy();
    expect(view.container.querySelector(`#${runBodyId}`)?.tagName).toBe("P");
    const runDetails = runSummary!.closest("details")!;
    runDetails.open = true;
    await fireEvent(runDetails, new Event("toggle"));
    expect(runSummary).toHaveAttribute("aria-expanded", "true");
  });

  it("captures the gap question as a grounded assumption draft", async () => {
    apiMocks.getSelectionChallenges.mockResolvedValue({ challenges: [challenge], stale: [] });
    const onTrackRisk = vi.fn();
    const view = render(EvidenceChallenge, {
      props: { jobId: "job-123", ideas: [idea], onTrackRisk },
    });

    await fireEvent.click(await view.findByRole("button", { name: "Save as a question to resolve" }));

    expect(view.queryByRole("button", { name: "Plan a test" })).not.toBeInTheDocument();
    expect(onTrackRisk).toHaveBeenCalledWith(expect.objectContaining({
      ideaId: "idea-signal-desk",
      ideaRevision: 3,
      lens: "demand",
      origin: { challengeId: "challenge-1", questionId: "pain_is_observed" },
      values: {
        statement: "The target customer repeatedly experiences this pain in the stated workflow.",
      },
      grounding: {
        statement: [expect.objectContaining({
          kind: "challenge_question",
          challengeId: "challenge-1",
          questionId: "pain_is_observed",
        })],
      },
    }));
  });

  it("offers a quiet branch entry for an open demand gap", async () => {
    apiMocks.getSelectionChallenges.mockResolvedValue({ challenges: [challenge], stale: [] });
    const onBranchDirection = vi.fn();
    const view = render(EvidenceChallenge, {
      props: { jobId: "job-123", ideas: [idea], onBranchDirection },
    });

    await fireEvent.click(await view.findByRole("button", { name: /Branch a new direction/ }));
    expect(onBranchDirection).toHaveBeenCalledOnce();
  });

  it("hides the branch entry when the case holds or the lens is not demand or competition", async () => {
    const supportedDemand: SelectionChallenge = {
      ...challenge,
      overall: "withstands",
      questions: challenge.questions.map((question) => ({ ...question, consensus: "supported" as const })),
    };
    const dependenciesGap: SelectionChallenge = { ...challenge, id: "challenge-2", lens: "dependencies" };
    apiMocks.getSelectionChallenges.mockResolvedValue({
      challenges: [supportedDemand, dependenciesGap],
      stale: [],
    });
    const view = render(EvidenceChallenge, {
      props: { jobId: "job-123", ideas: [idea], onBranchDirection: vi.fn() },
    });

    await view.findByText("Saved evidence supports this");
    expect(view.queryByRole("button", { name: /Branch a new direction/ })).not.toBeInTheDocument();

    await fireEvent.click(view.getByRole("tab", { name: /Can you build it\?/ }));
    await view.findByText("Review perspectives disagree");
    expect(view.queryByRole("button", { name: /Branch a new direction/ })).not.toBeInTheDocument();
  });

  it("follows the page-scoped candidate and exposes no local candidate dropdown", async () => {
    const secondIdea: SolutionPreview = {
      ...idea,
      idea_id: "idea-evidence-map",
      idea_revision: 2,
      solution_name: "Evidence Map",
    };
    apiMocks.runSelectionChallenge.mockImplementation(async (_jobId: string, input: {
      ideaId: string;
      ideaRevision: number;
    }) => ({
      challenge: { ...challenge, ideaId: input.ideaId, ideaRevision: input.ideaRevision },
      cached: false,
    }));
    const view = render(EvidenceChallenge, {
      props: {
        jobId: "job-123",
        ideas: [idea, secondIdea],
        candidateId: "idea-evidence-map",
      },
    });

    await waitFor(() => expect(apiMocks.getSelectionChallenges).toHaveBeenCalledWith("job-123"));
    // The candidate switcher lives in the cockpit scope strip now.
    expect(view.queryByRole("combobox")).not.toBeInTheDocument();

    await fireEvent.click(await view.findByRole("button", { name: "Check demand" }));
    await waitFor(() => expect(apiMocks.runSelectionChallenge).toHaveBeenCalledWith("job-123", {
      ideaId: "idea-evidence-map",
      ideaRevision: 2,
      lens: "demand",
    }));

    await view.rerender({ jobId: "job-123", ideas: [idea, secondIdea], candidateId: idea.idea_id });
    await fireEvent.click(await view.findByRole("button", { name: "Check demand" }));
    await waitFor(() => expect(apiMocks.runSelectionChallenge).toHaveBeenCalledWith("job-123", {
      ideaId: "idea-signal-desk",
      ideaRevision: 3,
      lens: "demand",
    }));
  });

  it("marks prior output stale instead of presenting it as current evidence", async () => {
    apiMocks.getSelectionChallenges.mockResolvedValue({
      challenges: [],
      stale: [{ ideaId: idea.idea_id, ideaRevision: 3, lens: "demand" }],
    });
    const view = render(EvidenceChallenge, {
      props: { jobId: "job-123", ideas: [idea] },
    });

    await waitFor(() => expect(view.getByText("Needs recheck")).toBeInTheDocument());
    expect(view.getByText("This review predates the current check method or evidence")).toBeInTheDocument();
    expect(view.getByRole("button", { name: "Recheck demand" })).toBeEnabled();
  });

  it("labels cited experiment evidence by how the result was observed", async () => {
    const experimentChallenge: SelectionChallenge = {
      ...challenge,
      evidenceSnapshot: experimentSources,
      questions: [{
        ...challenge.questions[0],
        skeptic: { ...challenge.questions[0].skeptic, evidenceKeys: ["E1", "E2"] },
        auditor: { ...challenge.questions[0].auditor, evidenceKeys: ["E1", "E2"] },
      }],
    };
    apiMocks.getSelectionChallenges.mockResolvedValue({
      challenges: [experimentChallenge],
      stale: [{ ideaId: idea.idea_id, ideaRevision: 3, lens: "demand" }],
    });
    const view = render(EvidenceChallenge, {
      props: { jobId: "job-123", ideas: [idea] },
    });

    expect(await view.findByRole("button", { name: "Check again" })).toBeEnabled();
    await fireEvent.click(view.getByText("2 cited sources"));
    expect(view.getByText("Observed hosted test")).toBeInTheDocument();
    expect(view.getByText("Owner-recorded external result")).toBeInTheDocument();
    expect(view.getByText("Hosted CTA test")).toBeInTheDocument();
    expect(view.getByText("External interview test")).toBeInTheDocument();
  });

  it("focuses the exact evidence gap selected from the decision-risk queue", async () => {
    apiMocks.getSelectionChallenges.mockResolvedValue({ challenges: [challenge], stale: [] });
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: vi.fn().mockReturnValue({ matches: true }),
    });
    Object.defineProperty(Element.prototype, "scrollIntoView", {
      configurable: true,
      value: vi.fn(),
    });

    const view = render(EvidenceChallenge, {
      props: {
        jobId: "job-123",
        ideas: [idea],
        focus: {
          requestId: 7,
          ideaId: idea.idea_id!,
          ideaRevision: 3,
          lens: "demand",
          challengeId: challenge.id,
          questionId: "pain_is_observed",
        },
      },
    });

    const heading = await view.findByRole("heading", { name: "Is the pain directly observed?" });
    await waitFor(() => expect(document.activeElement).toBe(heading));
  });

  it("opens owner evidence only when candidate, lens, challenge, and question provenance match", async () => {
    apiMocks.getSelectionChallenges.mockResolvedValue({ challenges: [challenge], stale: [] });
    const basePrefill = {
      requestId: "copilot-owner-evidence",
      ideaId: idea.idea_id!,
      ideaRevision: 3,
      lens: "demand" as const,
      values: {
        kind: "CUSTOMER_QUOTE" as const,
        position: "SUPPORTS" as const,
        title: "Buyer interview",
        content: "The buyer described a recurring weekly workflow.",
      },
    };
    const view = render(EvidenceChallenge, {
      props: {
        jobId: "job-123",
        ideas: [idea],
        ownerEvidencePrefill: {
          ...basePrefill,
          origin: { challengeId: challenge.id, questionId: "missing-question" },
        },
      },
    });

    expect(await view.findByRole("alert")).toHaveTextContent("question behind this draft is missing");
    expect(view.queryByRole("heading", { name: "Record what you learned" })).not.toBeInTheDocument();

    await view.rerender({
      jobId: "job-123",
      ideas: [idea],
      ownerEvidencePrefill: {
        ...basePrefill,
        requestId: "copilot-owner-evidence-current",
        origin: { challengeId: challenge.id, questionId: "pain_is_observed" },
      },
    });

    expect(await view.findByRole("heading", { name: "Record what you learned" })).toBeInTheDocument();
    expect(view.getByDisplayValue("The buyer described a recurring weekly workflow.")).toBeInTheDocument();
    expect(apiMocks.createSelectionOwnerEvidence).not.toHaveBeenCalled();
  });

  it("loads owner evidence once in the canonical ledger without a second tab count", async () => {
    apiMocks.getSelectionOwnerEvidence.mockResolvedValue({
      evidence: [{
        id: "evidence-1",
        jobId: "job-123",
        ideaId: idea.idea_id,
        ideaRevision: 3,
        lens: "demand",
        kind: "NOTE",
        position: "CONTEXT",
        title: "A note",
        content: "Something already known.",
        sourceUrl: null,
        observedAt: null,
        createdAt: "2026-07-16T00:00:00.000Z",
        retractedAt: null,
        retractionReason: null,
      }],
      editable: true,
    });
    const view = render(EvidenceChallenge, {
      props: { jobId: "job-123", ideas: [idea] },
    });

    await waitFor(() => expect(view.getByText(/1 saved/)).toBeInTheDocument());
    expect(apiMocks.getSelectionOwnerEvidence).toHaveBeenCalledTimes(1);
    const demandTab = view.getByRole("tab", { name: /Do people want it\?/ });
    expect(within(demandTab).queryByText(/note/)).not.toBeInTheDocument();
  });

  it("offers one lens-aware evidence action after the primary check action", async () => {
    const view = render(EvidenceChallenge, {
      props: { jobId: "job-123", ideas: [idea] },
    });

    expect(await view.findByText("See what your saved evidence says about demand")).toBeInTheDocument();
    expect(view.getByText("Free · reviews saved evidence only")).toBeInTheDocument();

    await waitFor(() => expect(apiMocks.getSelectionOwnerEvidence).toHaveBeenCalledTimes(1));
    expect(view.queryByText("Your evidence", { selector: "strong" })).not.toBeInTheDocument();
    const addActions = view.getAllByRole("button", { name: "Add your evidence" });
    expect(addActions).toHaveLength(1);
    await fireEvent.click(addActions[0]);
    expect(await view.findByRole("region", { name: "Record what you learned" })).toBeInTheDocument();
    expect(view.getByText("Your evidence", { selector: "strong" })).toBeInTheDocument();
  });

  it("labels the stale lens chip as outdated with a warning explanation", async () => {
    apiMocks.getSelectionChallenges.mockResolvedValue({
      challenges: [],
      stale: [{ ideaId: idea.idea_id, ideaRevision: 3, lens: "demand" }],
    });
    const view = render(EvidenceChallenge, {
      props: { jobId: "job-123", ideas: [idea] },
    });

    const chip = await view.findByText("Recheck");
    expect(chip.closest(".issue-badge")).toHaveAttribute(
      "title",
      "Needs recheck. This review predates the current check method or evidence.",
    );
    const demandTab = view.getByRole("tab", { name: /predates the current check method/ });
    expect(demandTab).toBeInTheDocument();
    // The dead in-result stale note is gone; the server never serializes
    // stale artifacts.
    expect(view.queryByText(/This result remains visible for context/)).not.toBeInTheDocument();
  });
});
