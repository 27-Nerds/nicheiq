import { cleanup, fireEvent, render, waitFor, within } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import DecisionCockpit from "../DecisionCockpit.svelte";
import { groupForMode } from "$lib/selection/labels";
import type { FounderFitArtifact } from "$lib/types/founderFit";
import type { SelectionDecisionProfile, SolutionPreview } from "$lib/types/job";
import type { SelectionChallenge } from "$lib/types/selectionChallenge";

describe("groupForMode", () => {
  it("maps market and fit to the compare group", () => {
    expect(groupForMode("market")).toBe("compare");
    expect(groupForMode("fit")).toBe("compare");
  });

  it("maps challenge, risk, and assumptions to the pressure group", () => {
    expect(groupForMode("challenge")).toBe("pressure");
    expect(groupForMode("risk")).toBe("pressure");
    expect(groupForMode("assumptions")).toBe("pressure");
  });
});

const apiMocks = vi.hoisted(() => ({
  getFounderFit: vi.fn(),
  runFounderFit: vi.fn(),
  getSelectionChallenges: vi.fn(),
  runSelectionChallenge: vi.fn(),
  getSelectionAssumptions: vi.fn(),
  createSelectionAssumption: vi.fn(),
  updateSelectionAssumption: vi.fn(),
  getSelectionOwnerEvidence: vi.fn(),
  createSelectionOwnerEvidence: vi.fn(),
  retractSelectionOwnerEvidence: vi.fn(),
}));

vi.mock("$lib/api", () => apiMocks);

function idea(name: string, overrides: Partial<SolutionPreview> = {}): SolutionPreview {
  return {
    idea_id: `idea-${name.toLowerCase().replaceAll(" ", "-")}`,
    solution_name: name,
    description: `${name} description`,
    value_proposition: `${name} value`,
    adjusted_composite_score: 0.6,
    market_fit_score: 0.55,
    technical_feasibility_score: 0.7,
    estimated_development_time: "4–6 weeks",
    ...overrides,
  };
}

describe("DecisionCockpit", () => {
  afterEach(cleanup);
  beforeEach(() => {
    apiMocks.getFounderFit.mockReset().mockResolvedValue({ analysis: null, stale: false });
    apiMocks.runFounderFit.mockReset();
    apiMocks.getSelectionChallenges.mockReset().mockResolvedValue({ challenges: [], stale: [] });
    apiMocks.runSelectionChallenge.mockReset();
    apiMocks.getSelectionAssumptions.mockReset().mockResolvedValue({ assumptions: [] });
    apiMocks.createSelectionAssumption.mockReset();
    apiMocks.updateSelectionAssumption.mockReset();
    apiMocks.getSelectionOwnerEvidence.mockReset().mockResolvedValue({ evidence: [], editable: true });
    apiMocks.createSelectionOwnerEvidence.mockReset();
    apiMocks.retractSelectionOwnerEvidence.mockReset();
  });

  it("keeps research scores and evidence visible as a side-by-side decision sheet", () => {
    const { getByRole } = render(DecisionCockpit, {
      props: {
        open: true,
        onClose: vi.fn(),
        ideas: [
          idea("Signal Desk", {
            adjusted_composite_score: 0.71,
            source_pain: "Teams miss recurring demand signals",
            critic_concern: "Buyer urgency is not yet proven",
          }),
          idea("Evidence Map", {
            adjusted_composite_score: 0.58,
            source_pain: "Research evidence stays fragmented",
            differentiation_locus: "Links each recommendation to its source",
          }),
        ],
      },
    });

    const dialog = getByRole("dialog", { name: "Compare shortlisted ideas" });
    expect(dialog).toHaveTextContent("Research findings stay separate from your preference");
    expect(dialog).toHaveTextContent("71/100");
    expect(dialog).toHaveTextContent("58/100");
    expect(dialog).toHaveTextContent("Teams miss recurring demand signals");
    expect(dialog).toHaveTextContent("Buyer urgency is not yet proven");
    expect(dialog).toHaveTextContent("Links each recommendation to its source");
  });

  it("keeps one exact candidate-set surface while giving each active view a semantic anchor", async () => {
    const view = render(DecisionCockpit, {
      props: {
        open: true,
        jobId: "job-123",
        onClose: vi.fn(),
        ideas: [
          idea("Signal Desk", { idea_revision: 2 }),
          idea("Evidence Map", { idea_revision: 4 }),
        ],
      },
    });
    const dialog = view.getByRole("dialog", { name: "Compare shortlisted ideas" });
    const surface = dialog.querySelector<HTMLElement>(
      '[data-annotation-surface="selection:decision-cockpit:shortlist:idea-signal-desk:2|idea-evidence-map:4"]',
    );

    expect(surface).not.toBeNull();
    expect(surface?.dataset.annotationAnchor).toBe(
      "selection:decision-cockpit:shortlist:idea-signal-desk:2|idea-evidence-map:4",
    );
    expect(surface?.querySelector(".cockpit-head")).not.toBeNull();
    expect(surface?.querySelector(".scope-strip")).not.toBeNull();
    expect(view.getByRole("tabpanel")).toHaveAttribute(
      "data-annotation-anchor",
      "selection:decision-cockpit:view:market",
    );

    await fireEvent.click(view.getByRole("tab", { name: "Fit for you" }));
    expect(dialog.querySelector("[data-annotation-surface]")).toBe(surface);
    expect(view.getByRole("tabpanel")).toHaveAttribute(
      "data-annotation-anchor",
      "selection:decision-cockpit:view:fit",
    );
  });

  it("passes the active view and exact candidate revisions to contextual analyst guidance", async () => {
    const onAskAnalyst = vi.fn();
    const ideas = [idea("Signal Desk", { idea_revision: 2 })];
    const view = render(DecisionCockpit, {
      props: {
        open: true,
        jobId: "job-123",
        tabGroup: "pressure",
        onClose: vi.fn(),
        onAskAnalyst,
        ideas,
      },
    });

    await fireEvent.click(view.getByRole("tab", { name: "Tracked assumptions" }));
    await fireEvent.click(view.getByRole("button", { name: "Ask analyst" }));

    expect(onAskAnalyst).toHaveBeenCalledWith("assumptions", ideas);
  });

  it("states the all-candidate scope as a passive record line on the market view", () => {
    const { getByRole } = render(DecisionCockpit, {
      props: {
        open: true,
        onClose: vi.fn(),
        ideas: [idea("Signal Desk"), idea("Evidence Map")],
      },
    });

    const dialog = getByRole("dialog", { name: "Compare shortlisted ideas" });
    const strip = dialog.querySelector<HTMLElement>(".scope-strip");
    expect(strip).not.toBeNull();
    expect(strip).toHaveTextContent("Scope · All 2 shortlisted");
    expect(strip).toHaveTextContent("Signal Desk");
    expect(strip).toHaveTextContent("Evidence Map");
    // Passive scope: the chips are not interactive.
    expect(strip?.querySelector("button")).toBeNull();
    expect(strip?.querySelector("[role='radiogroup']")).toBeNull();
  });

  it("names a single candidate in the scope record line instead of a count", () => {
    const { getByRole } = render(DecisionCockpit, {
      props: { open: true, onClose: vi.fn(), ideas: [idea("Signal Desk")] },
    });

    const strip = getByRole("dialog", { name: "Compare shortlisted ideas" })
      .querySelector<HTMLElement>(".scope-strip");
    expect(strip).toHaveTextContent("Scope · Signal Desk");
    expect(strip).not.toHaveTextContent("shortlisted");
  });

  it("switches the evidence-check candidate through the scope-strip chips", async () => {
    apiMocks.runSelectionChallenge.mockResolvedValue({
      challenge: demandChallenge("idea-evidence-map", 1),
      cached: false,
    });
    const view = render(DecisionCockpit, {
      props: {
        open: true,
        jobId: "job-123",
        initialMode: "challenge",
        tabGroup: "pressure",
        onClose: vi.fn(),
        ideas: [
          idea("Signal Desk", { idea_revision: 1 }),
          idea("Evidence Map", { idea_revision: 1 }),
        ],
      },
    });

    const group = view.getByRole("radiogroup", { name: "Candidate scope" });
    const first = within(group).getByRole("radio", { name: "Signal Desk" });
    const second = within(group).getByRole("radio", { name: "Evidence Map" });
    expect(first).toHaveAttribute("aria-checked", "true");
    expect(second).toHaveAttribute("aria-checked", "false");

    await fireEvent.click(second);
    expect(second).toHaveAttribute("aria-checked", "true");
    expect(first).toHaveAttribute("aria-checked", "false");

    await fireEvent.click(view.getByRole("button", { name: "Stress-test customer demand evidence" }));
    await waitFor(() => expect(apiMocks.runSelectionChallenge).toHaveBeenCalledWith("job-123", {
      ideaId: "idea-evidence-map",
      ideaRevision: 1,
      lens: "demand",
    }));
  });

  it("keeps the cockpit body as the scroll region and drops the decision-prompt footer", () => {
    const view = render(DecisionCockpit, {
      props: {
        open: true,
        onClose: vi.fn(),
        ideas: [idea("Signal Desk"), idea("Evidence Map")],
      },
    });

    const dialog = view.getByRole("dialog", { name: "Compare shortlisted ideas" });
    // Scroll contract: the tabpanel is the .cockpit-body scroll container and
    // the market table lives in .table-scroll, which owns both scroll axes.
    const panel = view.getByRole("tabpanel");
    expect(panel).toHaveClass("cockpit-body");
    expect(panel.querySelector(".table-scroll")).not.toBeNull();
    // The rhetorical footer is gone; only variant review renders a footer.
    expect(dialog.querySelector(".decision-note")).toBeNull();
    expect(view.queryByText("Decision prompt")).not.toBeInTheDocument();
  });

  it("shows founder constraints as a separate lens", () => {
    const profile: SelectionDecisionProfile = {
      preset: "solo_bootstrap",
      weeklyTime: "under_10",
      budget: "under_1k",
      team: "solo",
      revenueHorizon: "90_days",
      distributionAdvantages: ["seo"],
      strengths: "",
      hardConstraints: "",
    };
    const { getByRole } = render(DecisionCockpit, {
      props: {
        open: true,
        onClose: vi.fn(),
        ideas: [idea("Signal Desk"), idea("Evidence Map")],
        profile,
      },
    });

    const dialog = getByRole("dialog", { name: "Compare shortlisted ideas" });
    expect(dialog).toHaveTextContent("Your lens");
    expect(dialog).toHaveTextContent("under 10 hrs/week · under $1k · solo · revenue in 90 days");
  });

  it("closes through the shared workspace overlay control", async () => {
    const onClose = vi.fn();
    const { getByRole } = render(DecisionCockpit, {
      props: { open: true, onClose, ideas: [idea("Signal Desk"), idea("Evidence Map")] },
    });

    await fireEvent.click(getByRole("button", { name: "Close comparison" }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("uses the wider aligned grid for a three-idea shortlist", () => {
    const { getByLabelText } = render(DecisionCockpit, {
      props: {
        open: true,
        onClose: vi.fn(),
        ideas: [idea("Signal Desk"), idea("Evidence Map"), idea("Demand Probe")],
      },
    });

    expect(getByLabelText("Shortlisted idea comparison").firstElementChild).toHaveClass("three-ideas");
  });

  it("uses a two-column grid when reviewing one idea", () => {
    const { getByLabelText } = render(DecisionCockpit, {
      props: {
        open: true,
        onClose: vi.fn(),
        ideas: [idea("Signal Desk")],
      },
    });

    const comparison = getByLabelText("Shortlisted idea comparison").firstElementChild;
    expect(comparison).toHaveClass("single-idea");
    expect(comparison).not.toHaveClass("three-ideas");
  });

  it("sinks identical rows below differing rows and labels the score cell for screen readers", () => {
    const { getByRole } = render(DecisionCockpit, {
      props: {
        open: true,
        onClose: vi.fn(),
        ideas: [
          idea("Signal Desk", { adjusted_composite_score: 0.71, value_proposition: "Shared value" }),
          idea("Evidence Map", { adjusted_composite_score: 0.58, value_proposition: "Shared value" }),
        ],
      },
    });

    const dialog = getByRole("dialog", { name: "Compare shortlisted ideas" });
    expect(dialog.querySelector('[aria-label="71 out of 100"]')).not.toBeNull();
    expect(dialog.querySelector('[aria-label="58 out of 100"]')).not.toBeNull();

    const rowLabels = Array.from(dialog.querySelectorAll(".row-label"));
    const labelTexts = rowLabels.map((el) => el.textContent);
    // Every other row reads identically for both ideas (shared defaults), so
    // the differing "Research score" row surfaces first.
    expect(labelTexts[0]).toBe("Research score");
    const marketFitRow = rowLabels[labelTexts.indexOf("Market fit")];
    expect(marketFitRow).toHaveClass("is-uniform");
    const researchScoreRow = rowLabels[0];
    expect(researchScoreRow).not.toHaveClass("is-uniform");
  });

  it("keeps market and founder fit as peer views in the compare group", async () => {
    const { getByRole, queryByLabelText } = render(DecisionCockpit, {
      props: {
        open: true,
        jobId: "job-123",
        onClose: vi.fn(),
        ideas: [idea("Signal Desk", { idea_revision: 1 })],
      },
    });

    const navigation = getByRole("navigation", { name: "Comparison views" });
    expect(navigation).toHaveTextContent("Market");
    expect(navigation).toHaveTextContent("Fit for you");
    expect(navigation).not.toHaveTextContent("Biggest unknowns");
    expect(navigation).not.toHaveTextContent("Tracked assumptions");
    expect(navigation).not.toHaveTextContent("Evidence review");

    expect(queryByLabelText("Shortlisted idea comparison")).toBeInTheDocument();
    await fireEvent.click(getByRole("tab", { name: "Fit for you" }));
    expect(getByRole("heading", { name: "Challenge the shortlist against your real constraints" })).toBeInTheDocument();
  });

  it("keeps evidence check, decision risks, and assumption map as peer views in the pressure group", async () => {
    const { getByRole, queryByLabelText } = render(DecisionCockpit, {
      props: {
        open: true,
        jobId: "job-123",
        tabGroup: "pressure",
        onClose: vi.fn(),
        ideas: [idea("Signal Desk", { idea_revision: 1 })],
      },
    });

    expect(queryByLabelText("Shortlisted idea comparison")).not.toBeInTheDocument();
    expect(getByRole("heading", { name: "Try to break the case before you commit" })).toBeInTheDocument();
    await waitFor(() => expect(apiMocks.getSelectionChallenges).toHaveBeenCalledWith("job-123"));

    await fireEvent.click(getByRole("tab", { name: "Biggest unknowns" }));
    expect(getByRole("heading", { name: "What could change this decision?" })).toBeInTheDocument();
    await fireEvent.click(getByRole("tab", { name: "Tracked assumptions" }));
    expect(getByRole("heading", { name: "Make the decision hinge visible" })).toBeInTheDocument();
    await waitFor(() => expect(apiMocks.getSelectionAssumptions).toHaveBeenCalledWith("job-123"));
  });

  it("keeps the pressure-test navigation rail visible when opened directly into evidence check", async () => {
    const view = render(DecisionCockpit, {
      props: {
        open: true,
        jobId: "job-123",
        initialMode: "challenge",
        tabGroup: "pressure",
        onClose: vi.fn(),
        ideas: [idea("Signal Desk", { idea_revision: 1 })],
      },
    });

    const navigation = view.getByRole("navigation", { name: "Comparison views" });
    expect(navigation).toHaveTextContent("Biggest unknowns");
    expect(navigation).toHaveTextContent("Tracked assumptions");
    expect(navigation).toHaveTextContent("Evidence review");
    expect(navigation).not.toHaveTextContent("Market");
    expect(navigation).not.toHaveTextContent("Fit for you");
    expect(view.getByRole("tab", { name: "Evidence review" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(view.getByRole("heading", { name: "Try to break the case before you commit" })).toBeInTheDocument();
  });

  it("supports arrow-key navigation across comparison tabs", async () => {
    const view = render(DecisionCockpit, {
      props: {
        open: true,
        jobId: "job-123",
        initialMode: "market",
        onClose: vi.fn(),
        ideas: [idea("Signal Desk", { idea_revision: 1 })],
      },
    });

    const marketTab = view.getByRole("tab", { name: "Market" });
    await fireEvent.keyDown(marketTab, { key: "ArrowRight" });

    const founderTab = view.getByRole("tab", { name: "Fit for you" });
    expect(founderTab).toHaveAttribute("aria-selected", "true");
    expect(founderTab).toHaveAttribute("aria-controls", "cockpit-panel");
    expect(founderTab).toHaveFocus();
    expect(view.getByRole("tabpanel")).toHaveAttribute("aria-labelledby", "cockpit-tab-fit");
  });

  it("wraps arrow-key navigation within the active tab group instead of spilling into the other group", async () => {
    const compareView = render(DecisionCockpit, {
      props: {
        open: true,
        jobId: "job-123",
        initialMode: "market",
        onClose: vi.fn(),
        ideas: [idea("Signal Desk", { idea_revision: 1 })],
      },
    });
    const marketTab = compareView.getByRole("tab", { name: "Market" });
    await fireEvent.keyDown(marketTab, { key: "ArrowLeft" });
    const founderTab = compareView.getByRole("tab", { name: "Fit for you" });
    expect(founderTab).toHaveAttribute("aria-selected", "true");
    expect(founderTab).toHaveFocus();
    cleanup();

    const pressureView = render(DecisionCockpit, {
      props: {
        open: true,
        jobId: "job-123",
        initialMode: "assumptions",
        tabGroup: "pressure",
        onClose: vi.fn(),
        ideas: [idea("Signal Desk", { idea_revision: 1 })],
      },
    });
    const assumptionsTab = pressureView.getByRole("tab", { name: "Tracked assumptions" });
    await fireEvent.keyDown(assumptionsTab, { key: "ArrowRight" });
    const evidenceTab = pressureView.getByRole("tab", { name: "Evidence review" });
    expect(evidenceTab).toHaveAttribute("aria-selected", "true");
    expect(evidenceTab).toHaveFocus();
  });

  it("keeps founder-fit advice source-traceable and only pre-fills a test after owner action", async () => {
    const profile: SelectionDecisionProfile = {
      preset: "solo_bootstrap",
      weeklyTime: "under_10",
      budget: "under_1k",
      team: "solo",
      revenueHorizon: "90_days",
      distributionAdvantages: ["seo"],
      strengths: "Technical writing",
      hardConstraints: "No paid acquisition",
    };
    const signal = idea("Signal Desk", { idea_revision: 1 });
    const experiment = {
      ideaId: signal.idea_id!,
      ideaRevision: 1,
      assumptionType: "FEASIBILITY" as const,
      assumption: "A thin slice fits the weekly time budget.",
      whyCritical: "Otherwise the idea must be narrowed.",
      currentEvidence: "The current build estimate is four to six weeks.",
      method: "TECHNICAL_SPIKE" as const,
      evidenceSignal: "USAGE" as const,
      stimulus: "Build one end-to-end workflow.",
      audience: "Founder operator",
      channel: "Private development environment",
      primaryMetric: "Hours to working path",
      passThreshold: "Twelve hours or less",
      failThreshold: "More than twenty hours",
      measurementWindow: "Stop at twenty hours",
      sampleTarget: 1,
      costEstimate: "One weekend",
      passAction: "Run a customer test",
      failAction: "Narrow the mechanism",
      flatAction: "Remove one feature",
      invalidAction: "Document and retry once",
    };
    const analysis: FounderFitArtifact = {
      version: 1,
      inputFingerprint: "f".repeat(64),
      profileSnapshot: profile,
      ideaSnapshots: [{ idea_id: signal.idea_id, idea_revision: 1 }],
      model: "gpt-test",
      createdAt: "2026-07-16T00:00:00.000Z",
      results: [{
        ideaId: signal.idea_id!,
        ideaRevision: 1,
        ideaTitle: "Signal Desk",
        verdict: "needs_reshape",
        summary: "The market case is plausible, but the first slice is too broad for the available time.",
        strongestAdvantage: "Technical writing can support the reported SEO path.",
        blockingConflict: null,
        decisionChangingUnknown: "Whether one useful workflow fits into twelve hours.",
        sensitivity: "The verdict improves if the first release removes automated ingestion.",
        dimensions: [{
          dimension: "time",
          status: "unknown",
          summary: "The report gives a total estimate, not a thin-slice estimate.",
          profileFields: ["weeklyTime"],
          ideaFields: ["estimated_development_time"],
        }],
        suggestedExperiment: experiment,
      }],
    };
    apiMocks.runFounderFit.mockResolvedValue({ analysis, cached: false });
    const onTestUnknown = vi.fn();
    const onEvaluateFitReshape = vi.fn();
    const { getByRole, getByText, queryByText } = render(DecisionCockpit, {
      props: {
        open: true,
        jobId: "job-123",
        onClose: vi.fn(),
        onTestUnknown,
        onEvaluateFitReshape,
        ideas: [signal],
        profile,
      },
    });

    await waitFor(() => expect(apiMocks.getFounderFit).toHaveBeenCalledWith("job-123"));
    await fireEvent.click(getByRole("tab", { name: "Fit for you" }));
    await fireEvent.click(getByRole("button", { name: "Analyze fit for you" }));

    await waitFor(() => expect(getByText("Reshape first")).toBeInTheDocument());
    expect(getByText("profile.weeklyTime · idea.estimated_development_time")).toBeInTheDocument();
    expect(getByText("owner-only", { exact: false })).toBeInTheDocument();
    expect(queryByText("no score or shortlist changes", { exact: false })).not.toBeInTheDocument();
    expect(getByRole("button", { name: "Reshape to fit" })).toBeInTheDocument();
    expect(onTestUnknown).not.toHaveBeenCalled();

    await fireEvent.click(getByRole("button", { name: "Plan a test" }));
    expect(onTestUnknown).toHaveBeenCalledWith(experiment);
  });

  function demandChallenge(ideaId: string, ideaRevision: number): SelectionChallenge {
    return {
      id: "challenge-1",
      version: 1,
      inputFingerprint: "f".repeat(64),
      ideaId,
      ideaRevision,
      ideaTitle: "Signal Desk",
      lens: "demand",
      overall: "weakened",
      ideaSnapshot: { solution_name: "Signal Desk" },
      subjectSnapshot: [],
      evidenceSnapshot: [],
      questions: [{
        questionId: "pain_is_observed",
        consensus: "insufficient",
        skeptic: {
          questionId: "pain_is_observed",
          position: "insufficient",
          summary: "No recurring pain is captured.",
          subjectKeys: [],
          evidenceKeys: [],
          evidenceClass: "inference",
        },
        auditor: {
          questionId: "pain_is_observed",
          position: "insufficient",
          summary: "The record cannot answer this question.",
          subjectKeys: [],
          evidenceKeys: [],
          evidenceClass: "inference",
        },
      }],
      skepticModel: "model-skeptic",
      auditorModel: "model-auditor",
      promptVersion: 1,
      createdAt: "2026-07-16T00:00:00.000Z",
    };
  }

  it("routes a challenge finding into the assumption map without closing the cockpit", async () => {
    const signal = idea("Signal Desk", { idea_revision: 1 });
    apiMocks.getSelectionChallenges.mockResolvedValue({
      challenges: [demandChallenge(signal.idea_id!, 1)],
      stale: [],
    });
    const onClose = vi.fn();
    const view = render(DecisionCockpit, {
      props: {
        open: true,
        jobId: "job-123",
        initialMode: "challenge",
        tabGroup: "pressure",
        onClose,
        ideas: [signal],
      },
    });

    await fireEvent.click(await view.findByRole("button", { name: "Track as risk" }));

    expect(onClose).not.toHaveBeenCalled();
    // The editor modal backgrounds the cockpit chrome for AT while it is open,
    // so the tab rail is queried with hidden: the cockpit itself never closed.
    expect(view.getByRole("tab", { name: "Tracked assumptions", hidden: true })).toHaveAttribute("aria-selected", "true");
    expect(view.getByRole("dialog", { name: "Review evidence for shortlisted ideas", hidden: true })).toBeInTheDocument();
    const dialog = await view.findByRole("dialog", { name: "Track a key assumption" });
    expect(within(dialog).getByDisplayValue(
      "The target customer repeatedly experiences this pain in the stated workflow.",
    )).toBeInTheDocument();
    expect(within(dialog).getByText("Analyst draft · not saved")).toBeInTheDocument();
    expect(apiMocks.createSelectionAssumption).not.toHaveBeenCalled();
  });

  it("refuses to overwrite a dirty assumption editor with a newer analyst draft", async () => {
    const signal = idea("Signal Desk", { idea_revision: 1 });
    apiMocks.getSelectionChallenges.mockResolvedValue({
      challenges: [demandChallenge(signal.idea_id!, 1)],
      stale: [],
    });
    const baseProps = {
      open: true,
      jobId: "job-123",
      initialMode: "challenge" as const,
      tabGroup: "pressure" as const,
      onClose: vi.fn(),
      ideas: [signal],
    };
    const view = render(DecisionCockpit, { props: baseProps });

    await fireEvent.click(await view.findByRole("button", { name: "Track as risk" }));
    const dialog = await view.findByRole("dialog", { name: "Track a key assumption" });
    await fireEvent.input(within(dialog).getByLabelText(/What must be true\?/), {
      target: { value: "My unsaved owner wording" },
    });

    await view.rerender({
      ...baseProps,
      assumptionPrefill: {
        requestId: "copilot-1",
        ideaId: signal.idea_id!,
        ideaRevision: 1,
        lens: "demand" as const,
        origin: { challengeId: "challenge-1", questionId: "pain_is_observed" },
        grounding: {
          statement: [{
            ref: "Q1",
            kind: "challenge_question" as const,
            label: "Demand evidence check · pain is observed",
            challengeId: "challenge-1",
            questionId: "pain_is_observed",
          }],
        },
        rationale: "A newer analyst draft.",
        caveats: [],
        values: { statement: "A replacement analyst draft" },
      },
    });

    // Text/value queries instead of role queries: the test-harness rerender
    // replaces the whole props object, which re-runs both overlays' background
    // isolation effects and leaves the form overlay aria-hidden in jsdom. The
    // guard behavior under test is unaffected.
    expect(await within(dialog).findByText(/unsaved changes/)).toBeInTheDocument();
    expect(within(dialog).getByDisplayValue("My unsaved owner wording")).toBeInTheDocument();
    expect(within(dialog).queryByDisplayValue("A replacement analyst draft")).not.toBeInTheDocument();
  });
});

describe("DecisionCockpit parent and variant review", () => {
  afterEach(cleanup);

  it("shows exact lineage and lets the owner adopt the evaluated variant", async () => {
    const onClose = vi.fn();
    const onUseVariant = vi.fn().mockReturnValue({
      ok: true,
      message: "Replaced Signal Desk with the narrowed variant.",
    });
    const view = render(DecisionCockpit, {
      props: {
        open: true,
        onClose,
        onUseVariant,
        ideas: [
          idea("Signal Desk", { idea_revision: 3 }),
          idea("Agency Renewal Signal Desk", {
            idea_id: "idea-child",
            idea_revision: 1,
            synthesis_operation: "narrow",
          }),
        ],
        variantReview: {
          operation: "narrow",
          changeSummary: "Narrows the buyer and workflow to agency renewal reviews.",
          sourceContributions: ["Keep the recurring signal workflow."],
          requiresValidation: ["Validate the narrower buyer.", "Recheck weekly usage."],
          conclusionOutcome: "FAIL",
        },
      },
    });

    const dialog = view.getByRole("dialog", { name: "Compare parent and variant" });
    // Variant review states its own scope through the column labels; the
    // shortlist scope strip would mislabel the variant as shortlisted.
    expect(dialog.querySelector(".scope-strip")).toBeNull();
    expect(dialog).toHaveTextContent("Parent · rev 3");
    expect(dialog).toHaveTextContent("Narrowed variant · rev 1");
    expect(dialog).toHaveTextContent("Narrows the buyer and workflow");
    expect(dialog).toHaveTextContent("Keep the recurring signal workflow.");
    expect(dialog).toHaveTextContent("Validate the narrower buyer.");
    expect(dialog).toHaveTextContent("FAIL conclusion remains with the source.");
    expect(view.getByRole("region", { name: "Parent and variant comparison" })).toBeInTheDocument();

    await fireEvent.click(view.getByRole("button", { name: "Use variant in shortlist" }));
    expect(onUseVariant).toHaveBeenCalledOnce();
    expect(dialog).toHaveTextContent("Replaced Signal Desk with the narrowed variant.");

    await fireEvent.click(view.getByRole("button", { name: "Keep current shortlist" }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("compares both exact sources with a combined child and keeps their contributions distinct", () => {
    const view = render(DecisionCockpit, {
      props: {
        open: true,
        onClose: vi.fn(),
        onUseVariant: vi.fn(),
        ideas: [
          idea("Change Monitor", { idea_id: "source-1", idea_revision: 2 }),
          idea("Briefing Desk", { idea_id: "source-2", idea_revision: 4 }),
          idea("Agency Signal Desk", {
            idea_id: "combined-child",
            idea_revision: 1,
            synthesis_operation: "combine",
          }),
        ],
        variantReview: {
          operation: "combine",
          changeSummary: "Combines change detection with a client-ready briefing.",
          sourceContributions: [
            "Keep the alerting mechanism.",
            "Keep the client-ready summary.",
          ],
          requiresValidation: ["Validate that one agency buyer owns both workflows."],
          conclusionOutcome: null,
        },
      },
    });

    const dialog = view.getByRole("dialog", { name: "Compare sources and combined variant" });
    expect(dialog).toHaveTextContent("Source 1 · rev 2");
    expect(dialog).toHaveTextContent("Source 2 · rev 4");
    expect(dialog).toHaveTextContent("Combined variant · rev 1");
    expect(dialog).toHaveTextContent("Keep the alerting mechanism.");
    expect(dialog).toHaveTextContent("Keep the client-ready summary.");
    expect(dialog).toHaveTextContent("Validate that one agency buyer owns both workflows.");
    expect(view.getByRole(
      "region", { name: "Sources and combined variant comparison" },
    )).toBeInTheDocument();
  });
});
