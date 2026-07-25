import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, waitFor, within } from "@testing-library/svelte";
import ConceptForge from "../ConceptForge.svelte";
import {
  ApiError,
  archiveSelectionConceptSet,
  createSelectionConceptSet,
  getSelectionConceptSets,
  prepareSelectionConceptOption,
} from "$lib/api";
import type { IdeaSynthesisPatch } from "$lib/api";
import type { SolutionPreview } from "$lib/types/job";
import type { SelectionConceptSet } from "$lib/types/selectionConceptSet";
import { FORGE_RETRY_NOTE, PRICE_CHANGED_RETRY } from "$lib/selection/labels";

vi.mock("$lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("$lib/api")>();
  return {
    ...actual,
    getSelectionConceptSets: vi.fn(),
    createSelectionConceptSet: vi.fn(),
    prepareSelectionConceptOption: vi.fn(),
    archiveSelectionConceptSet: vi.fn(),
  };
});

const parent = {
  idea_id: "idea-signal",
  idea_revision: 3,
  solution_name: "Signal Desk",
  description: "A broad monitoring workflow.",
} as SolutionPreview;

const secondParent = {
  idea_id: "idea-renewal",
  idea_revision: 2,
  solution_name: "Renewal Radar",
  description: "A focused renewal-risk workflow.",
} as SolutionPreview;

const thirdParent = {
  idea_id: "idea-brief",
  idea_revision: 1,
  solution_name: "Brief Builder",
  description: "A weekly-brief workflow.",
} as SolutionPreview;

const patch: IdeaSynthesisPatch = {
  kind: "idea_synthesis",
  operation: "narrow",
  proposedTitle: "Weekly Signal Brief",
  proposedBrief: "One weekly review for a narrow renewal-risk workflow.",
  changeSummary: "Remove continuous monitoring and secondary workflows.",
  rationale: "This creates a smaller decision surface.",
  parents: [{
    ideaId: "idea-signal",
    ideaRevision: 3,
    solutionName: "Signal Desk",
    contribution: "Keep signal interpretation.",
  }],
  evidence: {
    sourceAnchors: [{
      ideaId: "idea-signal",
      ideaRevision: 3,
      candidateSnapshotSha256: "a".repeat(64),
    }],
    requiresValidation: ["Demand for a weekly workflow must be re-checked."],
  },
  newAssumptions: ["A weekly review is timely enough."],
};

function set(evaluatedOptionIds: string[] = []): SelectionConceptSet {
  const operations = ["narrow", "reposition", "adjacent"] as const;
  return {
    id: "660e8400-e29b-41d4-a716-446655440000",
    stale: false,
    createdAt: "2026-07-16T12:00:00.000Z",
    evaluatedOptionIds,
    artifact: {
      inputFingerprint: "f".repeat(64),
      purpose: "diverge",
      targetTradeoff: null,
      parents: [{
        ideaId: "idea-signal",
        ideaRevision: 3,
        solutionName: "Signal Desk",
        candidateSnapshotSha256: "a".repeat(64),
        pain: "Teams miss recurring signals",
        audience: "Solo SaaS founders",
      }],
      context: {
        reportSha256: "b".repeat(64),
        founderFitFingerprint: null,
        challengeFingerprints: [],
        conclusionFingerprints: [],
      },
      options: operations.map((operation, index) => {
        const assumptionId = `A${String(index + 1).repeat(10)}`;
        return {
          optionId: `O${String(index + 1).repeat(11)}`,
          operation,
          title: `${operation} direction`,
          brief: `A concrete ${operation} concept with a meaningfully different decision surface.`,
          changeSummary: `Change the ${operation} direction.`,
          rationale: "Expose one distinct trade-off.",
          parentContributions: [{
            ideaId: "idea-signal",
            ideaRevision: 3,
            solutionName: "Signal Desk",
            candidateSnapshotSha256: "a".repeat(64),
            pain: "Teams miss recurring signals",
            audience: "Solo SaaS founders",
            contribution: "Keep signal interpretation.",
          }],
          changedAxes: [{ axis: "scope" as const, from: "Broad", to: operation, reason: "Create a distinct option." }],
          retainedEvidence: ["The signal pain may still apply."],
          evidenceToRecheck: ["Demand for the changed workflow."],
          assumptions: [{
            assumptionId,
            type: "demand" as const,
            statement: `Buyers act on the ${operation} workflow.`,
            whyDecisionChanging: "Without action there is no demand signal.",
            consequenceIfFalse: "Park this option.",
          }],
          disqualifiers: ["No qualified buyer commits."],
          suggestedTest: {
            assumptionId,
            hypothesis: "Qualified buyers will book a call.",
            method: "BOOKED_CALL" as const,
            evidenceSignal: "SMALL_COMMITMENT" as const,
            audience: "Qualified solo SaaS founders",
            artifact: "One-page concept with booked-call CTA",
            primaryMetric: "Qualified booked-call rate",
            passThreshold: "At least 3 of 20 book",
            failThreshold: "Zero of 20 book",
            measurementWindow: "Seven days",
          },
        };
      }),
      model: "gpt-test",
      promptId: "selection-concept-forge",
      createdAt: "2026-07-16T12:00:00.000Z",
    },
  };
}

describe("ConceptForge", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getSelectionConceptSets).mockResolvedValue([]);
    vi.mocked(createSelectionConceptSet).mockResolvedValue({ set: set(), cached: false });
    vi.mocked(prepareSelectionConceptOption).mockResolvedValue({
      sourceMessageId: "proposal-message-1",
      patch,
      cached: false,
    });
    vi.mocked(archiveSelectionConceptSet).mockResolvedValue(undefined);
  });

  afterEach(cleanup);

  it("renders the shape overlay dialog with the brief view anchor", async () => {
    const view = render(ConceptForge, {
      props: {
        open: true,
        jobId: "job-1",
        parents: [parent],
        seedCost: 3,
        onEvaluate: vi.fn(),
        onClose: vi.fn(),
      },
    });

    await view.findByRole("heading", { name: "What should these options help you resolve?" });
    expect(view.getByRole("dialog", { name: "Branch a new direction" })).toBeInTheDocument();
    expect(view.getByText(/Signal Desk · rev 3/)).toBeInTheDocument();
    expect(view.getByRole("heading", {
      name: "What should these options help you resolve?",
    }).closest("[data-annotation-anchor]")).toHaveAttribute(
      "data-annotation-anchor",
      "selection:concept-forge:brief:diverge",
    );
  });

  it("moves selection and focus through only the rendered one-parent purposes", async () => {
    const view = render(ConceptForge, {
      props: {
        open: true,
        jobId: "job-1",
        parents: [parent],
        seedCost: 3,
        onEvaluate: vi.fn(),
        onClose: vi.fn(),
      },
    });

    const explore = await view.findByRole("radio", { name: /Explore directions/i });
    const reshape = view.getByRole("radio", { name: /Find a viable shape/i });
    expect(view.queryByRole("radio", { name: /Resolve the trade-off/i })).not.toBeInTheDocument();
    expect(explore).toHaveAttribute("tabindex", "0");
    expect(reshape).toHaveAttribute("tabindex", "-1");

    explore.focus();
    await fireEvent.keyDown(explore, { key: "ArrowRight" });
    await waitFor(() => expect(document.activeElement).toBe(reshape));
    expect(reshape).toHaveAttribute("aria-checked", "true");
    expect(reshape).toHaveAttribute("tabindex", "0");
    expect(explore).toHaveAttribute("tabindex", "-1");

    await fireEvent.keyDown(reshape, { key: "ArrowRight" });
    await waitFor(() => expect(document.activeElement).toBe(explore));
    expect(explore).toHaveAttribute("aria-checked", "true");
  });

  it("supports arrow, Home, and End navigation across all two-parent purposes", async () => {
    const view = render(ConceptForge, {
      props: {
        open: true,
        jobId: "job-1",
        parents: [parent, secondParent],
        seedCost: 3,
        onEvaluate: vi.fn(),
        onClose: vi.fn(),
      },
    });

    const explore = await view.findByRole("radio", { name: /Explore directions/i });
    const resolve = view.getByRole("radio", { name: /Resolve the trade-off/i });
    const reshape = view.getByRole("radio", { name: /Find a viable shape/i });
    expect(resolve).toHaveAttribute("aria-checked", "true");
    expect(resolve).toHaveAttribute("tabindex", "0");
    expect(explore).toHaveAttribute("tabindex", "-1");
    expect(reshape).toHaveAttribute("tabindex", "-1");

    resolve.focus();
    await fireEvent.keyDown(resolve, { key: "ArrowDown" });
    await waitFor(() => expect(document.activeElement).toBe(reshape));
    expect(reshape).toHaveAttribute("aria-checked", "true");

    await fireEvent.keyDown(reshape, { key: "Home" });
    await waitFor(() => expect(document.activeElement).toBe(explore));
    expect(explore).toHaveAttribute("aria-checked", "true");

    await fireEvent.keyDown(explore, { key: "End" });
    await waitFor(() => expect(document.activeElement).toBe(reshape));
    expect(reshape).toHaveAttribute("aria-checked", "true");

    await fireEvent.keyDown(reshape, { key: "ArrowUp" });
    await waitFor(() => expect(document.activeElement).toBe(resolve));
    expect(resolve).toHaveAttribute("aria-checked", "true");
  });

  it("creates three directions from the exact current parent revision", async () => {
    const view = render(ConceptForge, {
      props: {
        open: true,
        jobId: "job-1",
        parents: [parent],
        seedCost: 3,
        onEvaluate: vi.fn(),
        onClose: vi.fn(),
      },
    });

    await view.findByRole("heading", { name: "What should these options help you resolve?" });
    await fireEvent.click(view.getByRole("button", { name: /Generate directions/i }));

    await waitFor(() => expect(createSelectionConceptSet).toHaveBeenCalledWith("job-1", {
      purpose: "diverge",
      parents: [{ ideaId: "idea-signal", ideaRevision: 3 }],
    }));
    expect(await view.findByRole("heading", { name: "narrow direction" })).toBeInTheDocument();
    expect(view.getByRole("heading", { name: "reposition direction" })).toBeInTheDocument();
    expect(view.getByRole("heading", { name: "adjacent direction" })).toBeInTheDocument();
    expect(view.getByText("three unevaluated options")).toBeInTheDocument();
  });

  it("sends the specific tension into the concept set request", async () => {
    const view = render(ConceptForge, {
      props: {
        open: true,
        jobId: "job-1",
        parents: [parent],
        seedCost: 3,
        onEvaluate: vi.fn(),
        onClose: vi.fn(),
      },
    });

    await view.findByRole("heading", { name: "What should these options help you resolve?" });
    await fireEvent.input(view.getByLabelText(/Specific tension to explore/), {
      target: { value: "Speed to launch versus a stronger wedge" },
    });
    await fireEvent.click(view.getByRole("button", { name: /Generate directions/i }));

    await waitFor(() => expect(createSelectionConceptSet).toHaveBeenCalledWith("job-1", {
      purpose: "diverge",
      parents: [{ ideaId: "idea-signal", ideaRevision: 3 }],
      targetTradeoff: "Speed to launch versus a stronger wedge",
    }));
  });

  it("requires a second explicit click before routing one option into paid evaluation", async () => {
    vi.mocked(getSelectionConceptSets).mockResolvedValue([set()]);
    const onEvaluate = vi.fn().mockResolvedValue(true);
    const view = render(ConceptForge, {
      props: {
        open: true,
        jobId: "job-1",
        parents: [parent],
        seedCost: 3,
        onEvaluate,
        onClose: vi.fn(),
      },
    });

    const first = (await view.findAllByRole("button", { name: /Evaluate this option/i }))[0];
    await fireEvent.click(first);
    expect(prepareSelectionConceptOption).not.toHaveBeenCalled();
    expect(onEvaluate).not.toHaveBeenCalled();

    await fireEvent.click(view.getByRole("button", { name: /Confirm evaluation/i }));
    await waitFor(() => expect(prepareSelectionConceptOption).toHaveBeenCalledWith(
      "job-1",
      set().id,
      set().artifact.options[0].optionId,
      set().artifact.inputFingerprint,
    ));
    expect(onEvaluate).toHaveBeenCalledWith(patch, "proposal-message-1");
  });

  it("surfaces a not-started evaluation instead of staying in the preparing state", async () => {
    vi.mocked(getSelectionConceptSets).mockResolvedValue([set()]);
    const onEvaluate = vi.fn().mockResolvedValue(false);
    const view = render(ConceptForge, {
      props: {
        open: true,
        jobId: "job-1",
        parents: [parent],
        seedCost: 3,
        onEvaluate,
        onClose: vi.fn(),
      },
    });

    const first = (await view.findAllByRole("button", { name: /Evaluate this option/i }))[0];
    const firstCard = first.closest("article") as HTMLElement;
    await fireEvent.click(first);
    await fireEvent.click(view.getByRole("button", { name: /Confirm evaluation/i }));

    await waitFor(() => {
      const statuses = view.getAllByRole("status");
      expect(statuses.some((el) => el.textContent?.includes("Evaluation did not start"))).toBe(true);
    });
    expect(onEvaluate).toHaveBeenCalledTimes(1);
    // Confirming always disarms the gate (shared ConfirmGate contract): a
    // failed evaluation returns to the un-armed trigger, ready to retry.
    expect(within(firstCard).queryByRole("button", { name: /Confirm evaluation/i })).not.toBeInTheDocument();
    expect(within(firstCard).getByRole("button", { name: /Evaluate this option/i })).toBeEnabled();
  });

  it("lets the owner retry when saved directions fail to load", async () => {
    vi.mocked(getSelectionConceptSets)
      .mockRejectedValueOnce(new Error("Saved directions are temporarily unavailable."))
      .mockResolvedValueOnce([]);
    const view = render(ConceptForge, {
      props: {
        open: true,
        jobId: "job-1",
        parents: [parent],
        seedCost: 3,
        onEvaluate: vi.fn(),
        onClose: vi.fn(),
      },
    });

    expect(await view.findByRole("alert")).toHaveTextContent("Saved directions are temporarily unavailable.");
    await fireEvent.click(view.getByRole("button", { name: /Try again/i }));

    await view.findByRole("heading", { name: "What should these options help you resolve?" });
    expect(getSelectionConceptSets).toHaveBeenCalledTimes(2);
  });

  it("does not expose malformed response details when saved directions fail", async () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    vi.mocked(getSelectionConceptSets).mockRejectedValueOnce(
      new Error("JSON.parse: unexpected character at line 1 column 1 of the JSON data"),
    );

    const view = render(ConceptForge, {
      props: {
        open: true,
        jobId: "job-1",
        parents: [parent],
        seedCost: 3,
        onEvaluate: vi.fn(),
        onClose: vi.fn(),
      },
    });

    const alert = await view.findByRole("alert");
    expect(alert).toHaveTextContent("Could not load saved concept directions. Please try again.");
    expect(alert).not.toHaveTextContent("JSON.parse");
    expect(consoleError).toHaveBeenCalled();
    consoleError.mockRestore();
  });

  it("renders the scope picker at three parents, caps picks at two, and keys purposes off the picked subset", async () => {
    const view = render(ConceptForge, {
      props: {
        open: true,
        jobId: "job-1",
        parents: [parent, secondParent, thirdParent],
        seedCost: 3,
        onEvaluate: vi.fn(),
        onClose: vi.fn(),
      },
    });

    await view.findByRole("heading", { name: "What should these options help you resolve?" });
    expect(view.getByText("Pick up to 2 ideas to branch from.")).toBeInTheDocument();
    // Nothing picked yet: generation is gated and the two-parent purpose is absent.
    expect(view.getByRole("button", { name: /Generate directions/i })).toBeDisabled();
    expect(view.queryByRole("radio", { name: /Resolve the trade-off/i })).not.toBeInTheDocument();

    await fireEvent.click(view.getByRole("button", { name: /Signal Desk/ }));
    await waitFor(() =>
      expect(view.getByRole("button", { name: /Generate directions/i })).toBeEnabled(),
    );
    // One pick keeps the one-parent purpose list.
    expect(view.queryByRole("radio", { name: /Resolve the trade-off/i })).not.toBeInTheDocument();

    await fireEvent.click(view.getByRole("button", { name: /Renewal Radar/ }));
    // Two picks widen the purpose list and cap the picker.
    expect(await view.findByRole("radio", { name: /Resolve the trade-off/i })).toBeInTheDocument();
    expect(view.getByRole("button", { name: /Brief Builder/ })).toBeDisabled();

    await fireEvent.click(view.getByRole("button", { name: /Generate directions/i }));
    await waitFor(() => expect(createSelectionConceptSet).toHaveBeenCalledWith("job-1", {
      purpose: "resolve_tradeoff",
      parents: [
        { ideaId: "idea-renewal", ideaRevision: 2 },
        { ideaId: "idea-signal", ideaRevision: 3 },
      ],
    }));
  });

  it("reflects only picked parents in the header chips when the scope picker is up", async () => {
    const view = render(ConceptForge, {
      props: {
        open: true,
        jobId: "job-1",
        parents: [parent, secondParent, thirdParent],
        seedCost: 3,
        onEvaluate: vi.fn(),
        onClose: vi.fn(),
      },
    });

    await view.findByRole("heading", { name: "What should these options help you resolve?" });
    // Nothing picked yet: the header shows no source chips (the picker cards
    // below remain the selection surface).
    expect(view.queryByText(/Signal Desk · rev 3/)).not.toBeInTheDocument();

    await fireEvent.click(view.getByRole("button", { name: /Signal Desk/ }));
    expect(await view.findByText(/Signal Desk · rev 3/)).toBeInTheDocument();
    expect(view.queryByText(/Renewal Radar · rev 2/)).not.toBeInTheDocument();

    await fireEvent.click(view.getByRole("button", { name: /Renewal Radar/ }));
    expect(await view.findByText(/Renewal Radar · rev 2/)).toBeInTheDocument();
  });

  it("auto-selects all parents and renders no scope picker at two or fewer", async () => {
    const view = render(ConceptForge, {
      props: {
        open: true,
        jobId: "job-1",
        parents: [parent, secondParent],
        seedCost: 3,
        onEvaluate: vi.fn(),
        onClose: vi.fn(),
      },
    });

    await view.findByRole("heading", { name: "What should these options help you resolve?" });
    expect(view.queryByRole("button", { name: /Signal Desk/ })).not.toBeInTheDocument();
    expect(view.queryByText("Pick up to 2 ideas to branch from.")).not.toBeInTheDocument();
    // Both passed parents are live sources: the two-parent purpose is offered.
    expect(view.getByRole("radio", { name: /Resolve the trade-off/i })).toBeInTheDocument();
    expect(view.getByText(/Signal Desk · rev 3/)).toBeInTheDocument();
    expect(view.getByText(/Renewal Radar · rev 2/)).toBeInTheDocument();
  });

  it("opens clean from an analyst prefill so the first close dismisses immediately", async () => {
    const onClose = vi.fn();
    const view = render(ConceptForge, {
      props: {
        open: true,
        jobId: "job-1",
        parents: [parent],
        prefill: {
          requestId: "copilot-1",
          purpose: "diverge",
          targetTradeoff: "Speed to launch versus a stronger wedge",
          rationale: "The shortlist shares one unresolved tension.",
          caveats: [],
        },
        seedCost: 3,
        onEvaluate: vi.fn(),
        onClose,
      },
    });

    expect(await view.findByLabelText(/Specific tension to explore/)).toHaveValue(
      "Speed to launch versus a stronger wedge",
    );

    await fireEvent.keyDown(view.getByRole("dialog", { name: "Branch a new direction" }), {
      key: "Escape",
    });
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(view.queryByText(/unsent tension note/)).not.toBeInTheDocument();
  });

  it("still gates close behind a warning once the owner edits the prefilled tension", async () => {
    const onClose = vi.fn();
    const view = render(ConceptForge, {
      props: {
        open: true,
        jobId: "job-1",
        parents: [parent],
        prefill: {
          requestId: "copilot-2",
          purpose: "diverge",
          targetTradeoff: "Speed to launch versus a stronger wedge",
          rationale: "The shortlist shares one unresolved tension.",
          caveats: [],
        },
        seedCost: 3,
        onEvaluate: vi.fn(),
        onClose,
      },
    });

    await fireEvent.input(await view.findByLabelText(/Specific tension to explore/), {
      target: { value: "A different tension the owner actually typed" },
    });

    const dialog = view.getByRole("dialog", { name: "Branch a new direction" });
    await fireEvent.keyDown(dialog, { key: "Escape" });
    expect(onClose).not.toHaveBeenCalled();
    expect(view.getByText(/unsent tension note/)).toBeInTheDocument();

    await fireEvent.keyDown(dialog, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("restores the persisted set on an owner open even though a prefill is passed", async () => {
    vi.mocked(getSelectionConceptSets).mockResolvedValue([set()]);
    const view = render(ConceptForge, {
      props: {
        open: true,
        jobId: "job-1",
        parents: [parent],
        prefill: {
          requestId: "owner-open-1",
          purpose: "diverge",
          targetTradeoff: "",
          rationale: "",
          caveats: [],
        },
        seedCost: 3,
        onEvaluate: vi.fn(),
        onClose: vi.fn(),
      },
    });

    expect(await view.findByRole("heading", { name: "narrow direction" })).toBeInTheDocument();
    expect(getSelectionConceptSets).toHaveBeenCalledWith("job-1");
    expect(view.queryByText("Analyst brief")).not.toBeInTheDocument();
  });

  it("uses Compare-route prefetched directions without starting another request", async () => {
    const view = render(ConceptForge, {
      props: {
        open: true,
        jobId: "job-1",
        parents: [parent],
        initialSets: [set()],
        seedCost: 3,
        onEvaluate: vi.fn(),
        onClose: vi.fn(),
      },
    });

    expect(await view.findByRole("heading", { name: "narrow direction" })).toBeInTheDocument();
    expect(view.queryByText("Loading saved directions…")).not.toBeInTheDocument();
    expect(getSelectionConceptSets).not.toHaveBeenCalled();
  });

  it("uses a prefetched empty result without repeating the request", async () => {
    const view = render(ConceptForge, {
      props: {
        open: true,
        jobId: "job-1",
        parents: [parent],
        initialSets: [],
        seedCost: 3,
        onEvaluate: vi.fn(),
        onClose: vi.fn(),
      },
    });

    await view.findByRole("heading", { name: "What should these options help you resolve?" });
    expect(view.queryByText("Loading saved directions…")).not.toBeInTheDocument();
    expect(getSelectionConceptSets).not.toHaveBeenCalled();
  });

  it("shows no analyst aside on an owner open without a saved set", async () => {
    const view = render(ConceptForge, {
      props: {
        open: true,
        jobId: "job-1",
        parents: [parent],
        prefill: {
          requestId: "owner-open-2",
          purpose: "diverge",
          targetTradeoff: "",
          rationale: "",
          caveats: [],
        },
        seedCost: 3,
        onEvaluate: vi.fn(),
        onClose: vi.fn(),
      },
    });

    await view.findByRole("heading", { name: "What should these options help you resolve?" });
    expect(getSelectionConceptSets).toHaveBeenCalled();
    expect(view.queryByText("Analyst brief")).not.toBeInTheDocument();
    expect(view.queryByText("Not generated")).not.toBeInTheDocument();
  });

  it("shows the analyst brief aside and skips the saved-set restore for analyst prefills", async () => {
    vi.mocked(getSelectionConceptSets).mockResolvedValue([set()]);
    const view = render(ConceptForge, {
      props: {
        open: true,
        jobId: "job-1",
        parents: [parent],
        prefill: {
          requestId: "copilot-aside-1",
          purpose: "diverge",
          targetTradeoff: "",
          rationale: "The shortlist shares one unresolved tension.",
          caveats: ["Scores never transfer."],
        },
        seedCost: 3,
        onEvaluate: vi.fn(),
        onClose: vi.fn(),
      },
    });

    await view.findByRole("heading", { name: "What should these options help you resolve?" });
    expect(view.getByText("Analyst brief")).toBeInTheDocument();
    expect(view.getByText("The shortlist shares one unresolved tension.")).toBeInTheDocument();
    expect(view.getByText("Scores never transfer.")).toBeInTheDocument();
    expect(getSelectionConceptSets).not.toHaveBeenCalled();
  });

  it("marks an option evaluated, relabels its gate, and recounts the section label", async () => {
    vi.mocked(getSelectionConceptSets).mockResolvedValue([set()]);
    const onEvaluate = vi.fn().mockResolvedValue(true);
    const view = render(ConceptForge, {
      props: {
        open: true,
        jobId: "job-1",
        parents: [parent],
        seedCost: 3,
        onEvaluate,
        onClose: vi.fn(),
      },
    });

    const first = (await view.findAllByRole("button", { name: /Evaluate this option/i }))[0];
    const firstCard = first.closest("article") as HTMLElement;
    await fireEvent.click(first);
    await fireEvent.click(view.getByRole("button", { name: /Confirm evaluation/i }));

    await waitFor(() => expect(within(firstCard).getByText("Evaluated")).toBeInTheDocument());
    expect(within(firstCard).getByRole("button", { name: "Evaluated · run again" })).toBeEnabled();
    expect(view.getByText("two unevaluated options")).toBeInTheDocument();
    expect(view.getAllByRole("button", { name: "Evaluate this option" })).toHaveLength(2);
  });

  it("marks server-evaluated options across sessions from the set payload", async () => {
    const saved = set([set().artifact.options[0].optionId]);
    vi.mocked(getSelectionConceptSets).mockResolvedValue([saved]);
    const view = render(ConceptForge, {
      props: {
        open: true,
        jobId: "job-1",
        parents: [parent],
        seedCost: 3,
        onEvaluate: vi.fn(),
        onClose: vi.fn(),
      },
    });

    const firstCard = (await view.findByRole("heading", { name: "narrow direction" }))
      .closest("article") as HTMLElement;
    expect(within(firstCard).getByText("Evaluated")).toBeInTheDocument();
    expect(within(firstCard).getByRole("button", { name: "Evaluated · run again" })).toBeEnabled();
    expect(view.getByText("two unevaluated options")).toBeInTheDocument();
  });

  it("discards a saved set behind the gate and returns to the brief", async () => {
    vi.mocked(getSelectionConceptSets).mockResolvedValue([set()]);
    const view = render(ConceptForge, {
      props: {
        open: true,
        jobId: "job-1",
        parents: [parent],
        seedCost: 3,
        onEvaluate: vi.fn(),
        onClose: vi.fn(),
      },
    });

    await view.findByRole("heading", { name: "narrow direction" });
    await fireEvent.click(view.getByRole("button", { name: "Discard this set" }));
    // First click only arms the gate; nothing is archived yet.
    expect(archiveSelectionConceptSet).not.toHaveBeenCalled();
    expect(view.getByText("SET IS ARCHIVED · EVALUATED IDEAS KEEP THEIR PROVENANCE")).toBeInTheDocument();

    await fireEvent.click(view.getByRole("button", { name: "Discard this set" }));
    await waitFor(() => expect(archiveSelectionConceptSet).toHaveBeenCalledWith("job-1", set().id));

    await view.findByRole("heading", { name: "What should these options help you resolve?" });
    const statuses = view.getAllByRole("status");
    expect(statuses.some((el) => el.textContent?.includes("keep their provenance"))).toBe(true);
  });

  it("keeps the set and surfaces the failure when discarding fails", async () => {
    vi.mocked(getSelectionConceptSets).mockResolvedValue([set()]);
    vi.mocked(archiveSelectionConceptSet).mockRejectedValue(new Error("boom"));
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const view = render(ConceptForge, {
      props: {
        open: true,
        jobId: "job-1",
        parents: [parent],
        seedCost: 3,
        onEvaluate: vi.fn(),
        onClose: vi.fn(),
      },
    });

    await view.findByRole("heading", { name: "narrow direction" });
    await fireEvent.click(view.getByRole("button", { name: "Discard this set" }));
    await fireEvent.click(view.getByRole("button", { name: "Discard this set" }));

    expect(await view.findByRole("alert")).toHaveTextContent("Could not discard this set. Nothing changed.");
    expect(view.getByRole("heading", { name: "narrow direction" })).toBeInTheDocument();
    consoleError.mockRestore();
  });

  it("surfaces a structured guardrail message verbatim and swaps the footer to a retry line", async () => {
    vi.mocked(createSelectionConceptSet).mockRejectedValue(new ApiError(
      "With two candidates, one option must combine them, and the reply skipped it. Try again, or branch from a single candidate instead.",
      502,
      { error: "With two candidates, one option must combine them, and the reply skipped it. Try again, or branch from a single candidate instead.", code: "COMBINED_CONCEPT_OPTION_REQUIRED" },
    ));
    const view = render(ConceptForge, {
      props: {
        open: true,
        jobId: "job-1",
        parents: [parent, secondParent],
        seedCost: 3,
        onEvaluate: vi.fn(),
        onClose: vi.fn(),
      },
    });

    await view.findByRole("heading", { name: "What should these options help you resolve?" });
    await fireEvent.click(view.getByRole("button", { name: /Generate directions/i }));

    expect(await view.findByRole("alert")).toHaveTextContent(
      "With two candidates, one option must combine them, and the reply skipped it.",
    );
    expect(view.getByText(FORGE_RETRY_NOTE)).toBeInTheDocument();
    expect(view.queryByText(/Generating directions is free/)).not.toBeInTheDocument();
  });

  it("routes the footer Close through the dirty gate when a tension note is unsent", async () => {
    const onClose = vi.fn();
    const view = render(ConceptForge, {
      props: {
        open: true,
        jobId: "job-1",
        parents: [parent],
        seedCost: 3,
        onEvaluate: vi.fn(),
        onClose,
      },
    });

    await view.findByRole("heading", { name: "What should these options help you resolve?" });
    await fireEvent.input(view.getByLabelText(/Specific tension to explore/), {
      target: { value: "A tension note that has not been sent" },
    });

    await fireEvent.click(view.getByRole("button", { name: "Close" }));
    expect(onClose).not.toHaveBeenCalled();
    expect(view.getByText(/unsent tension note/)).toBeInTheDocument();

    await fireEvent.click(view.getByRole("button", { name: "Discard changes" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes from the footer Close on the first click when nothing is at risk", async () => {
    const onClose = vi.fn();
    const view = render(ConceptForge, {
      props: {
        open: true,
        jobId: "job-1",
        parents: [parent],
        seedCost: 3,
        onEvaluate: vi.fn(),
        onClose,
      },
    });

    await view.findByRole("heading", { name: "What should these options help you resolve?" });
    await fireEvent.click(view.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(view.queryByText(/unsent tension note/)).not.toBeInTheDocument();
  });

  it("states the shape cost contract on the first screen", async () => {
    const view = render(ConceptForge, {
      props: {
        open: true,
        jobId: "job-1",
        parents: [parent],
        seedCost: 3,
        onEvaluate: vi.fn(),
        onClose: vi.fn(),
      },
    });

    expect(await view.findByText(
      "Generating directions is free. Evaluating a direction costs 3 credits.",
    )).toBeInTheDocument();
  });

  it("surfaces the owner-page price-changed error inline after a failed evaluation", async () => {
    vi.mocked(getSelectionConceptSets).mockResolvedValue([set()]);
    const onEvaluate = vi.fn().mockResolvedValue(false);
    const view = render(ConceptForge, {
      props: {
        open: true,
        jobId: "job-1",
        parents: [parent],
        seedCost: 3,
        evaluateError: PRICE_CHANGED_RETRY,
        onEvaluate,
        onClose: vi.fn(),
      },
    });

    const first = (await view.findAllByRole("button", { name: /Evaluate this option/i }))[0];
    await fireEvent.click(first);
    await fireEvent.click(view.getByRole("button", { name: /Confirm evaluation/i }));

    await waitFor(() => expect(view.getByRole("alert")).toHaveTextContent(PRICE_CHANGED_RETRY));
    expect(view.queryByText(/Evaluation did not start/)).not.toBeInTheDocument();
  });

  it("explains why evaluation is disabled when no price is available", async () => {
    vi.mocked(getSelectionConceptSets).mockResolvedValue([set()]);
    const view = render(ConceptForge, {
      props: {
        open: true,
        jobId: "job-1",
        parents: [parent],
        seedCost: null,
        onEvaluate: vi.fn(),
        onClose: vi.fn(),
      },
    });

    expect(await view.findByText(/evaluation price is not available yet/i)).toBeInTheDocument();
    expect(view.queryByText(/Evaluating a direction costs/)).not.toBeInTheDocument();
    for (const button of view.getAllByRole("button", { name: /Evaluate this option/i })) {
      expect(button).toBeDisabled();
    }
  });

  it("states the evaluation cost in the options header before any gate is armed", async () => {
    vi.mocked(getSelectionConceptSets).mockResolvedValue([set()]);
    const view = render(ConceptForge, {
      props: {
        open: true,
        jobId: "job-1",
        parents: [parent],
        seedCost: 2,
        onEvaluate: vi.fn(),
        onClose: vi.fn(),
      },
    });

    expect(await view.findByText("Evaluating a direction costs 2 credits.")).toBeInTheDocument();
  });
});
