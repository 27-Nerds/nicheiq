import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, fireEvent, cleanup, waitFor, within } from "@testing-library/svelte";
import { page } from "$app/state";
import { goto, pushState, replaceState } from "$app/navigation";
import SelectionWorkbench from "../SelectionWorkbench.svelte";
import { seedIdea, regenerateIdeas, cancelSelectionOperation, getStageCosts, ApiError, createSelectionIdeaNarrowingProposal, getChatHistory, getSelectionChallenges, getSelectionConceptSets, getSelectionDecisionState, getSelectionExperiments, saveSelectionDecisionProfile, saveSelectionDraft, streamChat } from "$lib/api";
import { chatLedger } from "$lib/stores/chatLedger.svelte";
import { chatPanel } from "$lib/stores/chatPanel.svelte";
import { creditTopUp } from "$lib/stores/creditTopUp.svelte";
import type { SelectionDecisionProfile, SolutionPreview } from "$lib/types/job";
import type { RuledOutFinding } from "$lib/types/report";
import {
  readIdeaTheses,
  readUncoveredFamilies,
  type IdeaThesis,
  type ThesisMember,
  type UncoveredFamily,
} from "$lib/types/ideaThesis";
import pipelineIdeaTheses from "$lib/types/__tests__/fixtures/pipelineIdeaTheses.json";
import nicheVerdictExemplar from "$lib/selection/__tests__/fixtures/nicheDifficultyVerdict.exemplar.json";
import { SCORE_DEFINITIONS } from "$lib/utils/scoreDefinitions";
import { RANKED_IDEAS_ANCHOR } from "$lib/selection/rankedIdeas";
import { ideaPortfolioFingerprint } from "$lib/selection/ideaPortfolioFingerprint";
import { normalizeSolutionPreviews } from "$lib/utils/displayGuards";

// SelectionWorkbench embeds a REAL ChatThread (the seed card lives there), which loads
// history on mount — stub the network-touching bits of $lib/api so mounting/submitting
// never fires a real fetch. Mirrors GateWorkbench.test.ts's convention for this family.
vi.mock("$lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("$lib/api")>();
  return {
    ...actual,
    seedIdea: vi.fn(),
    cancelActiveJobOperation: vi.fn(),
    cancelSelectionOperation: vi.fn(),
    getStageCosts: vi.fn(),
    getChatHistory: vi.fn(() => Promise.resolve({ messages: [], weakPool: false })),
    streamChat: vi.fn(),
    regenerateIdeas: vi.fn(),
    createSelectionIdeaNarrowingProposal: vi.fn(),
    getSelectionConceptSets: vi.fn(() => Promise.resolve([])),
    getSelectionDecisionState: vi.fn(() => Promise.resolve({
      schemaVersion: 1,
      jobId: "job-1",
      status: "AWAITING_SELECTION",
      shortlist: { version: 0, items: [] },
      profile: null,
      founderFit: null,
      challenges: [],
      ownerEvidence: [],
      assumptions: [],
      experiments: [],
      conclusions: [],
      staleCounts: { shortlist: 0, profile: 0, founderFit: 0, challenges: 0, ownerEvidence: 0, assumptions: 0, experiments: 0, conclusions: 0, total: 0 },
      deepResearch: { eligible: false, optionalWorkRequired: false, blockers: ["NO_CURRENT_SHORTLIST"] },
      nextAction: { kind: "select_candidate", target: "shortlist", reason: "Choose one candidate.", required: true, ideas: [], lens: null, records: [] },
    })),
    createSelectionConceptSet: vi.fn(),
    prepareSelectionConceptOption: vi.fn(),
    getSelectionExperiments: vi.fn(() => Promise.resolve([])),
    getSelectionChallenges: vi.fn(() => Promise.resolve({ challenges: [], stale: [] })),
    getSelectionAssumptions: vi.fn(() => Promise.resolve({ assumptions: [] })),
    getSelectionOwnerEvidence: vi.fn(() => Promise.resolve({ evidence: [], editable: true })),
    getFounderFit: vi.fn(() => Promise.resolve({ analysis: null, stale: false })),
    selectSolution: vi.fn(),
    saveSelectionDecisionProfile: vi.fn(),
    saveSelectionDraft: vi.fn((
      _jobId: string, expectedVersion: number, items: unknown[],
    ) => Promise.resolve({ version: expectedVersion + 1, items })),
  };
});
function solution(name: string, overrides: Partial<SolutionPreview> = {}): SolutionPreview {
  return {
    solution_name: name,
    description: "A tool that does the thing",
    value_proposition: "Saves time",
    market_fit_score: 0.6,
    technical_feasibility_score: 0.6,
    estimated_development_time: "2 weeks",
    ...overrides,
  } as unknown as SolutionPreview;
}

/**
 * The stored fingerprint the pipeline writes — produced here by the SAME authority the
 * component consults, so these suites can never pass by two copies agreeing on the same
 * mistake. (This helper used to be a third re-implementation that, like the component's,
 * counted demoted candidates.)
 */
function portfolioFingerprint(solutions: SolutionPreview[]): string {
  const fingerprint = ideaPortfolioFingerprint(solutions);
  if (fingerprint === null) throw new Error("test pool is not fingerprintable");
  return fingerprint;
}

const SOLUTIONS = [
  solution("Alpha Idea", { idea_id: "idea-alpha", idea_revision: 1 }),
  solution("Beta Idea", { idea_id: "idea-beta", idea_revision: 1 }),
];

const STAGE_COSTS = { discovery: 5, deep_research: 15, landing_page: 5, regenerate_ideas: 2, seed_idea: 3 };

const baseProps = {
  jobId: "job-1",
  solutions: SOLUTIONS,
  creditBalance: 100,
  stageCosts: STAGE_COSTS,
  canRegenerate: true,
  ideaPortfolioSummaryFingerprint: portfolioFingerprint(SOLUTIONS),
  // The prop fails closed in the component; these suites describe a fully granted
  // owner. The ungated behaviour has its own describe block at the bottom of the file.
  decisionTools: true,
};

const OLD_DECISION_PROFILE: SelectionDecisionProfile = {
  preset: "solo_bootstrap",
  weeklyTime: "under_10",
  budget: "under_1k",
  team: "solo",
  revenueHorizon: "90_days",
  distributionAdvantages: ["seo"],
  strengths: "Writing",
  hardConstraints: "No calls",
};

const SAVED_DECISION_PROFILE: SelectionDecisionProfile = {
  ...OLD_DECISION_PROFILE,
  weeklyTime: "full_time",
};

/** The seed-card fixture ChatThread renders inside the embedded analyst window —
 *  distinct message id per test (see ChatThread.test.ts's note on localStorage
 *  dismissal keys leaking across tests that share a message id). */
function seedHistoryMessage(id: string) {
  return {
    id,
    gateStage: 5,
    role: "assistant" as const,
    content: "Here's your idea, priced for evaluation.",
    patchJson: {
      kind: "new_idea_seed" as const,
      free_text: "A tool that auto-reconciles freelance invoices",
      pain_ref: "Chasing late invoices",
      rationale: "Matches a validated pain with no direct incumbent",
    },
    truncated: false,
    createdAt: "2026-07-13T00:00:00.000Z",
  };
}

/** Phase 1b: analysis content (analyst notes, collaborator feedback, similar
 *  families, ruled-out list, coverage disclosures) files under the collapsed
 *  dossier appendix on the owner view — expand it before asserting contents. */
async function openAppendix(view: {
  findByRole: (role: string, options?: { name?: RegExp | string }) => Promise<HTMLElement>;
}) {
  await fireEvent.click(await view.findByRole("button", { name: /Discovery appendix/i }));
}

// DecisionGuide persists its toolbox-disclosure open/closed state to
// localStorage per job ("nicheiq:toolbox:<jobId>"). Every fixture in this file
// reuses jobId "job-1", so a manual toggle in one test would otherwise leak
// into every later test's initial render.
const originalPageUrl = page.url;
const originalPageState = page.state;

beforeEach(() => {
  localStorage.clear();
  page.url = new URL("http://localhost/jobs/job-1") as typeof page.url;
  page.state = {} as typeof page.state;
  vi.mocked(regenerateIdeas).mockResolvedValue({
    message: "Additional batch queued",
    operationId: "batch-operation-1",
    batchOrdinal: 2,
    focus: "auto",
  });
});

afterEach(() => {
  page.url = originalPageUrl;
  page.state = originalPageState;
});

describe("SelectionWorkbench — idea seed submit (402/409 CAS)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chatLedger.reset();
    chatPanel.open();
    creditTopUp.open = false;
    vi.mocked(getChatHistory).mockResolvedValue({ messages: [], weakPool: false } as never);
  });

  afterEach(() => {
    cleanup();
  });

  it("402 shows the credit top-up modal with the seed_idea cost", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [seedHistoryMessage("asst-seed-402")],
      weakPool: false,
    } as never);
    vi.mocked(seedIdea).mockRejectedValueOnce(new ApiError("Insufficient credits", 402, { balance: 1, required: 3 }));

    const { findByText } = render(SelectionWorkbench, { props: baseProps });

    await fireEvent.click(await findByText("Evaluate my idea"));

    await waitFor(() => expect(creditTopUp.open).toBe(true));
    expect(creditTopUp.context).toEqual({ balance: 1, required: 3, stageName: "idea evaluation" });
  });

  it("409 PRICE_CHANGED refreshes the price via getStageCosts and explains, without charging", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [seedHistoryMessage("asst-seed-409")],
      weakPool: false,
    } as never);
    vi.mocked(seedIdea).mockRejectedValueOnce(new ApiError("Price changed", 409));
    vi.mocked(getStageCosts).mockResolvedValueOnce({ ...STAGE_COSTS, seed_idea: 5 });

    const { findByText } = render(SelectionWorkbench, { props: baseProps });

    await fireEvent.click(await findByText("Evaluate my idea"));

    await findByText("The price changed. Review the new cost and try again.");
    expect(getStageCosts).toHaveBeenCalledTimes(1);
    // The refreshed price now shows on the (re-armed, since the request never
    // succeeded) card — never silently charges the stale number.
    await findByText("5");
  });

  it("a successful submit marks the seed pending in the durable ledger (poolMutationBusy's source of truth)", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [seedHistoryMessage("asst-seed-ok")],
      weakPool: false,
    } as never);
    vi.mocked(seedIdea).mockResolvedValueOnce({ message: "queued" });

    const { findByText } = render(SelectionWorkbench, { props: baseProps });

    await fireEvent.click(await findByText("Evaluate my idea"));

    await waitFor(() => expect(chatLedger.seedOutcome("asst-seed-ok")).toBe("pending"));
    expect(seedIdea).toHaveBeenCalledWith(
      "job-1",
      expect.objectContaining({
        free_text: "A tool that auto-reconciles freelance invoices",
        pain_ref: "Chasing late invoices",
        sourceMessageId: "asst-seed-ok",
        expectedCost: 3,
      }),
    );
  });

  it("settles cancellation against the current seed instead of an older terminal evaluation", async () => {
    const receipt = (
      id: string,
      sourceMessageId: string,
      event: "seed_submitted" | "seed_settled",
      outcome?: "accepted" | "cancelled",
    ) => ({
      id,
      gateStage: 5,
      role: "receipt" as const,
      content: "",
      patchJson: {
        kind: "ledger_event" as const,
        version: 1,
        event,
        ...(outcome ? { outcome } : {}),
        patch: {},
        rows: [],
        sourceMessageId,
      },
      truncated: false,
      createdAt: `2026-07-13T00:00:0${id.endsWith("current") ? 4 : 2}.000Z`,
    });
    const initial = {
      messages: [
        seedHistoryMessage("seed-old"),
        receipt("submitted-old", "seed-old", "seed_submitted"),
        receipt("settled-old", "seed-old", "seed_settled", "accepted"),
        seedHistoryMessage("seed-current"),
        receipt("submitted-current", "seed-current", "seed_submitted"),
      ],
      weakPool: false,
      activeOperation: { id: "dispatch-current", kind: "SEED_IDEA" as const, state: "AUTHORIZED" as const },
    };
    const settled = {
      ...initial,
      messages: [
        ...initial.messages,
        receipt("settled-current", "seed-current", "seed_settled", "cancelled"),
      ],
      activeOperation: null,
    };
    vi.mocked(getChatHistory)
      .mockResolvedValueOnce(initial as never)
      .mockResolvedValue(settled as never);
    vi.mocked(cancelSelectionOperation).mockResolvedValue({
      status: "cancelled",
      operationId: "dispatch-current",
      operationState: "CANCELLED",
      creditRefunded: 3,
    });
    const onSeedSettled = vi.fn();
    const view = render(SelectionWorkbench, { props: { ...baseProps, onSeedSettled } });

    await fireEvent.click(await view.findByRole("button", { name: "Cancel evaluation" }));

    await waitFor(() => expect(onSeedSettled).toHaveBeenCalledWith("cancelled"));
    expect(onSeedSettled).not.toHaveBeenCalledWith("accepted");
  });

  it("settlement (detected by polling the ledger) fires onSeedSettled — the parent's hook to force both refreshes", async () => {
    vi.useFakeTimers();
    const msgId = "asst-seed-settle";
    const stillPending = { messages: [seedHistoryMessage(msgId)], weakPool: false };
    const settled = {
      messages: [
        seedHistoryMessage(msgId),
        {
          id: "seed-receipt-settle",
          gateStage: 5,
          role: "receipt" as const,
          content: "",
          patchJson: {
            kind: "ledger_event" as const,
            version: 1,
            event: "seed_settled" as const,
            outcome: "accepted" as const,
            patch: {},
            rows: [],
            sourceMessageId: msgId,
          },
          truncated: false,
          createdAt: "2026-07-13T00:00:02.000Z",
        },
      ],
      weakPool: false,
    };
    vi.mocked(getChatHistory)
      .mockResolvedValueOnce(stillPending as never) // initial mount load
      .mockResolvedValueOnce(stillPending as never) // first poll tick — not settled yet
      .mockResolvedValue(settled as never); // second poll tick onward — settled

    vi.mocked(seedIdea).mockResolvedValueOnce({ message: "queued" });
    const onSeedSettled = vi.fn();

    const { findByText } = render(SelectionWorkbench, { props: { ...baseProps, onSeedSettled } });

    await fireEvent.click(await findByText("Evaluate my idea"));
    await vi.waitFor(() => expect(seedIdea).toHaveBeenCalledTimes(1));

    // First poll tick: still pending — no settlement callback yet.
    await vi.advanceTimersByTimeAsync(6000);
    expect(onSeedSettled).not.toHaveBeenCalled();

    // Second poll tick: the durable receipt has landed.
    await vi.advanceTimersByTimeAsync(6000);
    expect(onSeedSettled).toHaveBeenCalledTimes(1);
    expect(onSeedSettled).toHaveBeenCalledWith("accepted");

    vi.useRealTimers();
  });

  it(
    "the settlement poll survives well past the old 4-minute ceiling (now a ~20-minute backstop)",
    async () => {
      vi.useFakeTimers();
      const msgId = "asst-seed-longrun";
      const stillPending = { messages: [seedHistoryMessage(msgId)], weakPool: false };
      vi.mocked(getChatHistory).mockResolvedValue(stillPending as never);
      vi.mocked(seedIdea).mockResolvedValueOnce({ message: "queued" });
      const onSeedSettled = vi.fn();

      const { findByText } = render(SelectionWorkbench, { props: { ...baseProps, onSeedSettled } });

      await fireEvent.click(await findByText("Evaluate my idea"));
      await vi.waitFor(() => expect(seedIdea).toHaveBeenCalledTimes(1));

      // 10 minutes (100 ticks at 6s) — the OLD 40-attempt/4-minute ceiling would have given
      // up well before this point. A real seed run (tournament + score_wave + red-team + SEO
      // probes) routinely exceeds 4 minutes, so the card must still be evaluating here, not
      // silently stuck.
      await vi.advanceTimersByTimeAsync(10 * 60 * 1000);
      expect(onSeedSettled).not.toHaveBeenCalled();

      vi.useRealTimers();
    },
    20000,
  );

  it("resumes a durable pending seed after reload and settles it exactly once", async () => {
    vi.useFakeTimers();
    try {
      const msgId = "asst-seed-reload";
      const stillPending = {
        messages: [
          seedHistoryMessage(msgId),
          {
            id: "seed-receipt-pending",
            gateStage: 5,
            role: "receipt" as const,
            content: "",
            patchJson: {
              kind: "ledger_event" as const,
              version: 1,
              event: "seed_submitted" as const,
              patch: {},
              rows: [],
              sourceMessageId: msgId,
            },
            truncated: false,
            createdAt: "2026-07-13T00:00:01.000Z",
          },
        ],
        weakPool: false,
      };
      const settled = {
        messages: [
          ...stillPending.messages,
          {
            id: "seed-receipt-settled",
            gateStage: 5,
            role: "receipt" as const,
            content: "",
            patchJson: {
              kind: "ledger_event" as const,
              version: 1,
              event: "seed_settled" as const,
              outcome: "accepted" as const,
              patch: {},
              rows: [],
              sourceMessageId: msgId,
            },
            truncated: false,
            createdAt: "2026-07-13T00:00:02.000Z",
          },
        ],
        weakPool: false,
      };
      vi.mocked(getChatHistory)
        .mockResolvedValueOnce(stillPending as never)
        .mockResolvedValue(settled as never);
      const onSeedSettled = vi.fn();

      render(SelectionWorkbench, { props: { ...baseProps, onSeedSettled } });
      await vi.waitFor(() => expect(chatLedger.seedOutcome(msgId)).toBe("pending"));
      await vi.advanceTimersByTimeAsync(6000);

      expect(onSeedSettled).toHaveBeenCalledTimes(1);
      expect(onSeedSettled).toHaveBeenCalledWith("accepted");
    } finally {
      vi.useRealTimers();
    }
  });

  it("keeps seed recovery context after timeout and lets a manual check settle it", async () => {
    vi.useFakeTimers();
    try {
      const msgId = "asst-seed-stalled";
      const stillPending = {
        messages: [
          seedHistoryMessage(msgId),
          {
            id: "seed-receipt-pending",
            gateStage: 5,
            role: "receipt" as const,
            content: "",
            patchJson: {
              kind: "ledger_event" as const,
              version: 1,
              event: "seed_submitted" as const,
              patch: {},
              rows: [],
              sourceMessageId: msgId,
            },
            truncated: false,
            createdAt: "2026-07-13T00:00:01.000Z",
          },
        ],
        weakPool: false,
      };
      const settled = {
        messages: [
          ...stillPending.messages,
          {
            id: "seed-receipt-settled",
            gateStage: 5,
            role: "receipt" as const,
            content: "",
            patchJson: {
              kind: "ledger_event" as const,
              version: 1,
              event: "seed_settled" as const,
              outcome: "demoted" as const,
              patch: {},
              rows: [],
              sourceMessageId: msgId,
            },
            truncated: false,
            createdAt: "2026-07-13T00:00:02.000Z",
          },
        ],
        weakPool: false,
      };
      vi.mocked(getChatHistory).mockResolvedValue(stillPending as never);
      const onSeedSettled = vi.fn();
      const view = render(SelectionWorkbench, { props: { ...baseProps, onSeedSettled } });

      await vi.waitFor(() => expect(chatLedger.seedOutcome(msgId)).toBe("pending"));
      await vi.advanceTimersByTimeAsync(200 * 6000);
      expect(view.getByRole("button", { name: "Check for the result" })).toBeInTheDocument();

      vi.mocked(getChatHistory).mockResolvedValue(settled as never);
      await fireEvent.click(view.getByRole("button", { name: "Check for the result" }));
      await vi.waitFor(() => expect(onSeedSettled).toHaveBeenCalledTimes(1));
      expect(onSeedSettled).toHaveBeenCalledWith("demoted");
    } finally {
      vi.useRealTimers();
    }
  }, 20000);
});

describe("SelectionWorkbench — poolMutationBusy gates pool-mutating controls", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chatLedger.reset();
    chatPanel.open();
    vi.mocked(getChatHistory).mockResolvedValue({ messages: [], weakPool: false } as never);
  });

  afterEach(() => {
    cleanup();
  });

  it("a pending seed (durable, e.g. from a reload) disables regenerate and shortlist toggles", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [
        {
          id: "seed-receipt-busy",
          gateStage: 5,
          role: "receipt" as const,
          content: "",
          patchJson: {
            kind: "ledger_event" as const,
            version: 1,
            event: "seed_submitted" as const,
            patch: {},
            rows: [],
            sourceMessageId: "asst-seed-busy",
          },
          truncated: false,
          createdAt: "2026-07-13T00:00:00.000Z",
        },
      ],
      weakPool: false,
    } as never);

    const { findByText, findByRole, getByLabelText } = render(SelectionWorkbench, { props: baseProps });

    // chatLedger.hasPendingSeed only becomes true once the mocked history resolves.
    await waitFor(() => expect(chatLedger.hasPendingSeed).toBe(true));

    const regenBtn = await findByRole("button", { name: /Branch a new direction/ }) as HTMLButtonElement;
    expect(regenBtn.disabled).toBe(true);

    const shortlistCheckbox = getByLabelText("Select Alpha Idea") as HTMLInputElement;
    expect(shortlistCheckbox.disabled).toBe(true);
  });

  it("with no pending seed and affordable credits, regenerate and shortlist stay enabled", async () => {
    const { findByRole, getByLabelText } = render(SelectionWorkbench, { props: baseProps });

    const regenBtn = await findByRole("button", { name: /Branch a new direction/ }) as HTMLButtonElement;
    expect(regenBtn.disabled).toBe(false);

    const shortlistCheckbox = getByLabelText("Select Alpha Idea") as HTMLInputElement;
    expect(shortlistCheckbox.disabled).toBe(false);
  });
});

describe("SelectionWorkbench — ruled-out panel: idea name primary + 'Your idea' badge", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chatLedger.reset();
    chatPanel.open();
    vi.mocked(getChatHistory).mockResolvedValue({ messages: [], weakPool: false } as never);
  });

  afterEach(() => {
    cleanup();
  });

  const RULED_OUT: RuledOutFinding[] = [
    {
      pain_title: "Chasing late invoices",
      idea_name: "InvoiceChaser",
      source_frame: "user_seed",
      reason: "Thin market signal",
      market_fit: 0.2,
      market_fit_band: "low",
      prior_tier: "winner",
      source: "demoted_winner",
      evidence: "Only a handful of mentions",
      idea: solution("InvoiceChaser", {
        market_fit_score: 0.2,
        short_description: "Automates invoice follow-up",
      }),
    },
    {
      pain_title: "Manual reconciliation",
      reason: "No buyer identified",
      market_fit: 0.15,
      market_fit_band: "very-low",
      prior_tier: "backfill",
      source: "backfill_rejected",
      evidence: "",
    },
  ];

  it("renders idea_name as the primary label with the pain as secondary provenance, badged 'Your idea' for user_seed", async () => {
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, examinedRuledOut: RULED_OUT },
    });
    const { findByText, queryByText } = view;
    await openAppendix(view);

    await findByText("InvoiceChaser");
    await findByText("Your idea");
    // The pain title still renders, but as secondary provenance, not the headline.
    await findByText("Chasing late invoices");

    // The second (portfolio-backfill) entry has no idea_name and is not a seed —
    // falls back to the pain title as primary, with no badge.
    await findByText("Manual reconciliation");
    expect(queryByText("Your idea")).not.toBeNull(); // sanity: exactly one badge exists
    expect(document.querySelectorAll(".ruled-out-badge")).toHaveLength(1);
  });

  it("labels an accepted unanchored submitted idea without inventing a pain", async () => {
    const unanchored = solution("Esports Fantasy Cards", {
      source_frame: "user_seed",
      unanchored_hypothesis: true,
      source_pain: null,
      pain_points_addressed: [],
    });
    const { findByText } = render(SelectionWorkbench, {
      props: { ...baseProps, solutions: [unanchored], examinedRuledOut: [] },
    });

    await findByText("No validated pain match");
  });

  it("opens a submitted ruled-out idea in the read-only details view", async () => {
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, examinedRuledOut: RULED_OUT },
    });
    const { findByRole, findByText } = view;
    await openAppendix(view);

    await fireEvent.click(await findByRole("button", { name: /InvoiceChaser/ }));
    await findByRole("dialog", { name: "Ruled-out analysis: InvoiceChaser" });
    await findByText("Automates invoice follow-up");
  });

  it("rewrites internal ruled-out reasons from the real exemplar", async () => {
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        examinedRuledOut: [{
          ...RULED_OUT[0],
          reason: "This batch result duplicated the existing candidate 'NDCShiftVet', so it was not appended.",
        }],
      },
    });
    await openAppendix(view);

    expect(await view.findByText(
      "This direction was already represented by 'NDCShiftVet', so it was not added again.",
    )).toBeInTheDocument();
    expect(view.container.textContent).not.toMatch(/batch result|not appended/i);
  });

  it("opens summary analysis for a legacy ruled-out finding without an idea payload", async () => {
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, examinedRuledOut: RULED_OUT },
    });
    const { findByRole } = view;
    await openAppendix(view);

    await fireEvent.click(await findByRole("button", { name: /Manual reconciliation/ }));
    const dialog = await findByRole("dialog", { name: "Ruled-out analysis: Manual reconciliation" });
    expect(dialog).toHaveTextContent("No buyer identified");
  });

  it("keeps ruled-out findings visible as one appendix section", async () => {
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, examinedRuledOut: RULED_OUT },
    });
    await openAppendix(view);

    expect(
      await view.findByRole("heading", { name: "Ideas that did not clear the market-fit check" }),
    ).toBeVisible();
    expect(view.getByText("InvoiceChaser")).toBeVisible();
    expect(view.queryByRole("button", { name: /Examined & ruled out/i })).toBeNull();
  });

  it("explains the section and opens full analysis for a generated idea", async () => {
    const generatedFinding: RuledOutFinding = {
      ...RULED_OUT[1],
      idea_name: "ReconcileFlow",
      idea: solution("ReconcileFlow", {
        short_description: "Matches transactions and flags reconciliation gaps",
        value_proposition: "Cuts the time spent checking mismatched records",
      }),
    };
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, examinedRuledOut: [generatedFinding] },
    });
    const { findByRole, findByText } = view;
    await openAppendix(view);

    await findByText(
      "These concepts were examined, then screened out before the ranked ideas were presented. Open an idea to review the evidence and assumptions behind that decision.",
    );
    await fireEvent.click(await findByRole("button", { name: /ReconcileFlow/ }));
    await findByText("Matches transactions and flags reconciliation gaps");
    await findByText("Cuts the time spent checking mismatched records");
  });

  it("does not turn a shortened prose recommendation into an idea reference", async () => {
    chatPanel.close();
    const proMatchDesk = solution("ProMatchDesk (CS2+Dota 2)", {
      idea_id: "idea-pro-match-desk",
      idea_revision: 1,
    });
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: [proMatchDesk],
        ideaPortfolioSummaryFingerprint: portfolioFingerprint([proMatchDesk]),
        examinedRuledOut: [],
        ideaPortfolioSummary: "ProMatchDesk is the strongest reporting workflow.",
      },
    });

    expect(await view.findByLabelText("Discovery take")).toHaveTextContent(
      "stored recommendation is not bound to exact current idea revisions",
    );
    expect(view.queryByRole(
      "button", { name: /^ProMatchDesk \(CS2\+Dota 2\) ?, open details$/ },
    )).toBeNull();
  });

  it("withholds the entire unbound portfolio narrative from selection guidance", async () => {
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        ideaPortfolioSummary: [
          "The pool has moderate market fit overall.",
          "Free incumbents make willingness to pay the central risk.",
          "Alpha Idea most deserves deeper validation because it has the clearest buyer.",
        ].join("\n\n"),
      },
    });

    const verdict = await view.findByLabelText("Discovery take");
    expect(verdict).toHaveTextContent("stored recommendation is not bound to exact current idea revisions");
    expect(verdict).not.toHaveTextContent("most deserves deeper validation");

    const alphaRow = document.querySelector('[data-solution-name="Alpha Idea"]');
    const betaRow = document.querySelector('[data-solution-name="Beta Idea"]');
    expect(alphaRow).not.toHaveTextContent("Recommended");
    expect(betaRow).not.toHaveTextContent("Recommended");

    expect(view.queryByRole("button", { name: /Discovery appendix/i })).toBeNull();
    expect(view.queryByText("The pool has moderate market fit overall.")).toBeNull();
    expect(view.queryByText("Free incumbents make willingness to pay the central risk.")).toBeNull();
  });

  it("withholds a stored strongest claim when the current review marks its idea premise-unproven", async () => {
    const killed = solution("Killed Idea", {
      idea_id: "idea-killed",
      idea_revision: 1,
      adjusted_composite_score: 0.9,
      red_team_verdict: "killed",
      red_team_caveats: ["No evidence establishes the premise."],
    });
    const intact = solution("Intact Idea", {
      idea_id: "idea-intact",
      idea_revision: 1,
      adjusted_composite_score: 0.8,
    });
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: [killed, intact],
        ideaPortfolioSummaryFingerprint: portfolioFingerprint([killed, intact]),
        ideaPortfolioSummary: "Killed Idea is the strongest candidate to validate first.",
      },
    });

    const take = await view.findByLabelText("Discovery take");
    expect(take).toHaveTextContent("stored recommendation is not bound to exact current idea revisions");
    expect(take).not.toHaveTextContent("strongest candidate");
    expect(view.queryByText("Recommended")).toBeNull();
  });

  it("does not promote a runner-up from a sentence whose named winner is premise-unproven", async () => {
    const killed = solution("Killed A", {
      idea_id: "idea-killed-a",
      idea_revision: 1,
      adjusted_composite_score: 0.9,
      red_team_verdict: "killed",
    });
    const eligible = solution("Eligible B", {
      idea_id: "idea-eligible-b",
      idea_revision: 1,
      adjusted_composite_score: 0.8,
    });
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: [killed, eligible],
        ideaPortfolioSummaryFingerprint: portfolioFingerprint([killed, eligible]),
        ideaPortfolioSummary: "Killed A is the strongest candidate, while Eligible B is a distant runner-up.",
      },
    });

    expect(await view.findByLabelText("Discovery take")).not.toHaveTextContent("distant runner-up");
    expect(view.queryByText("Recommended")).toBeNull();
    expect(view.queryByRole("note", {
      name: "Why the top-scoring idea is not the recommendation",
    })).toBeNull();
  });

  it("withholds an unbound directive in an earlier summary sentence", async () => {
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        ideaPortfolioSummary: (
          "Recommend Ghost Candidate over Alpha Idea. The pool remains uncertain."
        ),
      },
    });

    const take = await view.findByLabelText("Discovery take");
    expect(take).toHaveTextContent(
      "stored recommendation is not bound to exact current idea revisions",
    );
    expect(take).not.toHaveTextContent("Ghost Candidate");
    expect(document.querySelectorAll(".analyst-pick")).toHaveLength(0);
  });

  it.each([
    "Ghost Candidate ranks strongest for validation.",
    "Alpha Idea is clearly the strongest for validation.",
    "Alpha Idea — strongest for validation — has a narrow evidence base.",
    "Alpha Idea ranks first for validation.",
    "Alpha Idea should be chosen first.",
    "Alpha Idea: strongest for validation.",
  ])("withholds alternative recommendation grammar: %s", async (analysis) => {
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, ideaPortfolioSummary: analysis },
    });

    const take = await view.findByLabelText("Discovery take");
    expect(take).toHaveTextContent(
      "stored recommendation is not bound to exact current idea revisions",
    );
    expect(take).not.toHaveTextContent(analysis);
    expect(document.querySelectorAll(".analyst-pick")).toHaveLength(0);
  });

  it.each([
    "Ghost Candidate ranked first for validation.",
    "Alpha Idea was ranked first for validation.",
    "Validate Alpha Idea first.",
    "Choose Alpha Idea first.",
    "Alpha Idea is the leading candidate for validation.",
    "Alpha Idea is the clear winner for validation.",
    "Ghost Candidate ranked first for validation. The pool remains uncertain.",
  ])("withholds ranking-role prose regardless of tense or sentence position: %s", async (analysis) => {
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, ideaPortfolioSummary: analysis },
    });

    const take = await view.findByLabelText("Discovery take");
    expect(take).toHaveTextContent(
      "stored recommendation is not bound to exact current idea revisions",
    );
    expect(take).not.toHaveTextContent("ranked first for validation");
    expect(take).not.toHaveTextContent("leading candidate for validation");
    expect(take).not.toHaveTextContent("clear winner for validation");
    expect(document.querySelectorAll(".analyst-pick")).toHaveLength(0);
  });

  it("withholds candidate-specific prose whose structured role is unknown", async () => {
    const analysis = "For Alpha Idea, the evidence remains strongest in billing urgency.";
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, ideaPortfolioSummary: analysis },
    });

    const take = await view.findByLabelText("Discovery take");
    expect(take).toHaveTextContent("stored recommendation is not bound to exact current idea revisions");
    expect(take).not.toHaveTextContent("billing urgency");
    expect(document.querySelectorAll(".analyst-pick")).toHaveLength(0);
  });

  it("withholds descriptive portfolio prose because its structured role is unknown", async () => {
    const analysis = "The strongest evidence concerns billing urgency, not candidate preference.";
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, ideaPortfolioSummary: analysis },
    });

    const take = await view.findByLabelText("Discovery take");
    expect(take).toHaveTextContent("stored recommendation is not bound to exact current idea revisions");
    expect(take).not.toHaveTextContent(analysis);
    expect(document.querySelectorAll(".analyst-pick")).toHaveLength(0);
  });

  it("withholds an explicit recommendation whose candidate name is ambiguous", async () => {
    const first = solution("Same Name", {
      idea_id: "idea-same-1",
      idea_revision: 1,
      adjusted_composite_score: 0.9,
    });
    const second = solution("Same Name", {
      idea_id: "idea-same-2",
      idea_revision: 1,
      adjusted_composite_score: 0.5,
    });
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        interactive: false,
        solutions: [first, second],
        ideaPortfolioSummaryFingerprint: portfolioFingerprint([first, second]),
        ideaPortfolioSummary: "Same Name is the strongest candidate to validate first.",
      },
    });

    const take = await view.findByLabelText("Discovery take");
    expect(take).toHaveTextContent("stored recommendation is not bound to exact current idea revisions");
    expect(take).not.toHaveTextContent("strongest candidate");
    expect(view.queryByText("Recommended")).toBeNull();
  });

  it("does not promote a real runner-up when the named winner is unknown", async () => {
    const alpha = solution("Alpha", {
      idea_id: "idea-alpha-known",
      idea_revision: 1,
      adjusted_composite_score: 0.8,
    });
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: [alpha],
        ideaPortfolioSummaryFingerprint: portfolioFingerprint([alpha]),
        ideaPortfolioSummary: "Ghost Candidate is the strongest candidate, while Alpha is a distant runner-up.",
      },
    });

    const take = await view.findByLabelText("Discovery take");
    expect(take).toHaveTextContent("stored recommendation is not bound to exact current idea revisions");
    expect(take).not.toHaveTextContent("Ghost Candidate");
    expect(view.queryByText("Recommended")).toBeNull();
  });

  it("rejects a recommendation name shared by current and ruled-out records", async () => {
    const collision = solution("Collision", {
      idea_id: "idea-current-collision",
      idea_revision: 1,
      adjusted_composite_score: 0.9,
    });
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: [collision],
        examinedRuledOut: [{
          ...RULED_OUT[0],
          idea_name: "Collision",
          reason: "A different historical candidate with the same working name.",
        }],
        ideaPortfolioSummaryFingerprint: portfolioFingerprint([collision]),
        ideaPortfolioSummary: "Collision is the strongest candidate to validate first.",
      },
    });

    expect(await view.findByLabelText("Discovery take")).toHaveTextContent(
      "stored recommendation is not bound to exact current idea revisions",
    );
    expect(view.queryByText("Recommended")).toBeNull();
  });

  it("does not expose a codename from unbound recommendation prose", async () => {
    const codenameIdeas = [
      solution("AlphaIdeaCodename", {
        idea_id: "idea-codename-alpha",
        idea_revision: 1,
        headline: "Alpha invoice chaser",
      }),
      solution("Beta Idea", { idea_id: "idea-codename-beta", idea_revision: 1 }),
    ];
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: codenameIdeas,
        ideaPortfolioSummaryFingerprint: portfolioFingerprint(codenameIdeas),
        ideaPortfolioSummary: "AlphaIdeaCodename most deserves deeper validation.",
      },
    });

    const verdict = await view.findByLabelText("Discovery take");
    expect(verdict).toHaveTextContent("stored recommendation is not bound to exact current idea revisions");
    expect(verdict).not.toHaveTextContent("AlphaIdeaCodename");
  });

  it("does not badge any idea from free-form recommendation prose", async () => {
    render(SelectionWorkbench, {
      props: {
        ...baseProps,
        ideaPortfolioSummary: [
          "Alpha Idea has the clearer buyer signal.",
          "Beta Idea is more novel but carries more execution risk.",
          "Alpha Idea most deserves deeper validation because it has the clearest buyer.",
        ].join(" "),
      },
    });

    const alphaRow = document.querySelector('[data-solution-name="Alpha Idea"]');
    const betaRow = document.querySelector('[data-solution-name="Beta Idea"]');
    expect(alphaRow).not.toHaveTextContent("Recommended");
    expect(betaRow).not.toHaveTextContent("Recommended");
    expect(document.querySelectorAll(".analyst-pick")).toHaveLength(0);
  });

  it("uses score authority for order and Suggested next despite recommendation prose", async () => {
    vi.mocked(getSelectionDecisionState).mockResolvedValueOnce({
      schemaVersion: 1,
      jobId: "job-1",
      status: "AWAITING_SELECTION",
      shortlist: { version: 0, items: [] },
      profile: null,
      founderFit: null,
      challenges: [],
      ownerEvidence: [],
      assumptions: [],
      experiments: [],
      conclusions: [],
      staleCounts: { shortlist: 0, profile: 0, founderFit: 0, challenges: 0, ownerEvidence: 0, assumptions: 0, experiments: 0, conclusions: 0, total: 0 },
      deepResearch: { eligible: false, optionalWorkRequired: false, blockers: ["NO_CURRENT_SHORTLIST"] },
      nextAction: {
        kind: "select_candidate",
        target: "shortlist",
        reason: "Review the first stored candidate.",
        required: true,
        ideas: [{ ideaId: "idea-matchboard", ideaRevision: 1, title: "Parts-Ready Matchboard" }],
        lens: null,
        records: [],
      },
    } as never);
    const ideas = [
      solution("Parts-Ready Matchboard", {
        idea_id: "idea-matchboard",
        idea_revision: 1,
        headline: "Find Tomorrow’s Best Appliance Callback",
        adjusted_composite_score: 0.48,
      }),
      solution("Parts-Ready Dispatch Control", {
        idea_id: "idea-dispatch",
        idea_revision: 1,
        headline: "Parts-Ready Dispatch Control for Appliance Repair",
        adjusted_composite_score: 0.9,
        red_team_verdict: "killed",
      }),
      solution("Appliance Ledger", {
        idea_id: "idea-ledger",
        idea_revision: 1,
        headline: "Auditable Appliance Service History Reconciliation",
        adjusted_composite_score: 0.5,
      }),
      solution("Model-to-Repair Decision Desk", {
        idea_id: "idea-model",
        idea_revision: 1,
        headline: "Model-to-Serial Repair Decision Workspace",
        adjusted_composite_score: 0.49,
      }),
    ];
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: ideas,
        ideaPortfolioSummaryFingerprint: portfolioFingerprint(ideas),
        ideaPortfolioSummary: "Appliance Ledger and Model-to-Repair Decision Desk are the only candidates that deserve further validation.",
      },
    });

    const table = view.getByRole("table", { name: "Ranked ideas" });
    await waitFor(() => expect(table.querySelectorAll("[data-solution-name]")).toHaveLength(4));
    const orderedNames = [...table.querySelectorAll<HTMLElement>("[data-solution-name]")]
      .map((row) => row.dataset.solutionName);
    expect(orderedNames).toEqual([
      "Parts-Ready Dispatch Control",
      "Appliance Ledger",
      "Model-to-Repair Decision Desk",
      "Parts-Ready Matchboard",
    ]);
    expect(table).not.toHaveTextContent("Recommended");

    const suggested = await view.findByRole("button", {
      name: "Review Auditable Appliance Service History Reconciliation",
    });
    expect(suggested).not.toHaveTextContent("Parts-Ready Matchboard");
    await fireEvent.click(suggested);
    expect(await view.findByRole("dialog", {
      name: "Solution details: Auditable Appliance Service History Reconciliation",
    })).toBeInTheDocument();
  });

  it("keeps a validate seed visually pinned without turning its row position into rank or guidance", async () => {
    vi.mocked(getSelectionDecisionState).mockResolvedValueOnce({
      schemaVersion: 1,
      jobId: "job-1",
      status: "AWAITING_SELECTION",
      shortlist: { version: 0, items: [] },
      profile: null,
      founderFit: null,
      challenges: [],
      ownerEvidence: [],
      assumptions: [],
      experiments: [],
      conclusions: [],
      staleCounts: { shortlist: 0, profile: 0, founderFit: 0, challenges: 0, ownerEvidence: 0, assumptions: 0, experiments: 0, conclusions: 0, total: 0 },
      deepResearch: { eligible: false, optionalWorkRequired: false, blockers: ["NO_CURRENT_SHORTLIST"] },
      nextAction: {
        kind: "select_candidate",
        target: "shortlist",
        reason: "Review the first stored candidate.",
        required: true,
        ideas: [{ ideaId: "idea-seed", ideaRevision: 1, title: "My seed idea" }],
        lens: null,
        records: [],
      },
    } as never);
    const ideas = [
      solution("My seed idea", {
        idea_id: "idea-seed",
        idea_revision: 1,
        source_frame: "user_seed",
        generation_operation_id: "validate",
        adjusted_composite_score: 0.43,
      }),
      solution("Unproven leader", {
        idea_id: "idea-killed",
        idea_revision: 1,
        headline: "Unproven high score",
        adjusted_composite_score: 0.75,
        red_team_verdict: "killed",
      }),
      solution("Strongest eligible", {
        idea_id: "idea-strong",
        idea_revision: 1,
        headline: "Strongest supported candidate",
        adjusted_composite_score: 0.65,
      }),
      solution("Middle candidate", {
        idea_id: "idea-middle",
        idea_revision: 1,
        adjusted_composite_score: 0.55,
      }),
    ];
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: ideas,
        groupByThesis: false,
        pinnedIdeaKeys: ["idea-seed:1"],
        ideaPortfolioSummaryFingerprint: portfolioFingerprint(ideas),
      },
    });

    const table = view.getByRole("table", { name: "Ranked ideas" });
    await waitFor(() => expect(table.querySelectorAll("[data-solution-name]")).toHaveLength(4));
    const rows = [...table.querySelectorAll<HTMLElement>("[data-solution-name]")];
    expect(rows[0]?.dataset.solutionName).toBe("My seed idea");
    expect(rows[0]?.querySelector(".cell-rank")).toHaveTextContent("4");

    const suggested = await view.findByRole("button", {
      name: "Review Strongest supported candidate",
    });
    expect(suggested).not.toHaveTextContent("My seed idea");
    expect(suggested).not.toHaveTextContent("Unproven high score");
  });

  it("does not create idea links from unbound portfolio prose", async () => {
    chatPanel.close();
    const { findByLabelText } = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        examinedRuledOut: RULED_OUT,
        ideaPortfolioSummary: "InvoiceChaser was examined but ruled out.",
      },
    });

    expect(await findByLabelText("Discovery take")).toHaveTextContent(
      "stored recommendation is not bound to exact current idea revisions",
    );
    expect(document.querySelector('button[aria-label^="InvoiceChaser"]')).toBeNull();
  });

  it("withholds an unbound recommendation even when its fingerprint matches", async () => {
    const reversedFingerprint = portfolioFingerprint([...SOLUTIONS].reverse());
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        ideaPortfolioSummaryFingerprint: reversedFingerprint,
        ideaPortfolioSummary: "Alpha Idea is the strongest candidate to validate first.",
      },
    });

    expect(await view.findByLabelText("Discovery take")).toHaveTextContent(
      "stored recommendation is not bound to exact current idea revisions",
    );
    expect(view.queryByText("Recommended")).toBeNull();
  });

  it.each([
    { interactive: true, decisionTools: true, fingerprint: "stale-fingerprint" },
    { interactive: true, decisionTools: false, fingerprint: undefined },
    { interactive: false, decisionTools: false, fingerprint: "stale-fingerprint" },
    { interactive: false, decisionTools: false, fingerprint: undefined },
  ])("shows the exact-revision warning for unbound prose: %o", async ({ interactive, decisionTools, fingerprint }) => {
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        interactive,
        decisionTools,
        ideaPortfolioSummaryFingerprint: fingerprint,
        ideaPortfolioSummary: "Ghost Candidate wins the validation ranking.",
      },
    });

    const take = await view.findByLabelText("Discovery take");
    expect(take).toHaveTextContent(
      "stored recommendation is not bound to exact current idea revisions",
    );
    expect(take).not.toHaveTextContent("Ghost Candidate");
  });

  it("does not create a phantom warning for whitespace-only portfolio prose", () => {
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        interactive: true,
        decisionTools: false,
        ideaPortfolioSummaryFingerprint: undefined,
        ideaPortfolioSummary: " \n\t ",
      },
    });

    expect(view.queryByLabelText("Discovery take")).toBeNull();
  });

  it("degrades when the pool changes without a summary recompute", async () => {
    const currentPool = Array.from({ length: 12 }, (_, index) => solution(
      `Idea ${index + 1}`,
      {
        idea_id: `idea-${index + 1}`,
        idea_revision: 1,
        adjusted_composite_score: (61 - index) / 100,
      },
    ));
    const originalPool = currentPool.slice(0, 6);
    const staleGuidance = "Idea 1 and Idea 5 deserve deeper validation next.";
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: currentPool,
        ideaPortfolioSummaryFingerprint: portfolioFingerprint(originalPool),
        ideaPortfolioSummary: staleGuidance,
      },
    });

    const take = await view.findByLabelText("Discovery take");
    expect(take).toHaveTextContent("Discovery take unavailable");
    expect(take).toHaveTextContent(
      "stored recommendation is not bound to exact current idea revisions",
    );
    expect(view.queryByText(staleGuidance)).toBeNull();
    expect(document.querySelectorAll(".analyst-pick")).toHaveLength(0);
    expect(view.getByRole("table", { name: "Ranked ideas" }))
      .toHaveTextContent("Idea 12");
  });

  it("recognizes the current pool but still withholds unbound recommendation prose", async () => {
    // The stored fingerprint skips demoted/absorbed (Python's visible_ideas(), mirrored in
    // backend/src/utils/ideaPortfolioFingerprint.ts). normalizeSolutionPreviews does NOT —
    // it keeps them — so a component-local fingerprint that counted them would see a
    // different pool than the pipeline did and kill guidance that is in fact current.
    const rawPool = [
      solution("Alpha Idea", { idea_id: "idea-alpha", idea_revision: 1 }),
      solution("Beta Idea", { idea_id: "idea-beta", idea_revision: 1 }),
      solution("Merged Idea", {
        idea_id: "idea-merged", idea_revision: 1, candidate_status: "absorbed",
      }),
      solution("Dropped Idea", {
        idea_id: "idea-dropped", idea_revision: 1, candidate_status: "demoted",
      }),
    ];
    const { solutions: displayed } = normalizeSolutionPreviews(rawPool);
    expect(displayed).toHaveLength(4);

    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: displayed,
        ideaPortfolioSummaryFingerprint: portfolioFingerprint(rawPool),
        ideaPortfolioSummary: "Alpha Idea is the strongest candidate to validate first.",
      },
    });

    expect(await view.findByLabelText("Discovery take")).toHaveTextContent(
      "stored recommendation is not bound to exact current idea revisions",
    );
  });

  it("fails closed when the display layer drops a candidate the summary covered", async () => {
    // normalizeSolutionPreviews (displayGuards.ts) drops entries with no solution_name, so a
    // malformed/legacy pool reaches the workbench SHORTER than the pool the pipeline
    // fingerprinted. There is no signal here that a candidate went missing, and guidance
    // written about an idea the reader cannot see is exactly finding D2 — withhold.
    const rawPool = [
      solution("Alpha Idea", { idea_id: "idea-alpha", idea_revision: 1 }),
      solution("Beta Idea", { idea_id: "idea-beta", idea_revision: 1 }),
      solution("", { idea_id: "idea-nameless", idea_revision: 1 }),
    ];
    const { solutions: displayed, invalidCount } = normalizeSolutionPreviews(rawPool);
    expect(invalidCount).toBe(1);

    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: displayed,
        ideaPortfolioSummaryFingerprint: portfolioFingerprint(rawPool),
        ideaPortfolioSummary: "Alpha Idea is the strongest candidate to validate first.",
      },
    });

    const take = await view.findByLabelText("Discovery take");
    expect(take).toHaveTextContent("Discovery take unavailable");
    expect(view.queryByText("Alpha Idea is the strongest candidate to validate first.")).toBeNull();
  });

  it("degrades gracefully for a legacy summary with no fingerprint", async () => {
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        ideaPortfolioSummaryFingerprint: null,
        ideaPortfolioSummary: "Alpha Idea is the strongest candidate to validate first.",
      },
    });

    const take = await view.findByLabelText("Discovery take");
    expect(take).toHaveTextContent("Discovery take unavailable");
    expect(take).toHaveTextContent(
      "stored recommendation is not bound to exact current idea revisions",
    );
    expect(view.queryByText("Alpha Idea is the strongest candidate to validate first.")).toBeNull();
  });

  /**
   * THE SECOND, INDEPENDENT ROUTE FOR `idea_portfolio_summary`, PINNED ON A VALUE THAT
   * DISCRIMINATES. `buyerFacingReport` takes this field through `buyerFacingVerdictNarrative`
   * at the REPORT boundary; this component reaches the raw prop and forks it again in a
   * `$derived` of its own. Both were covered against not being sanitised at all and NEITHER
   * against being on the wrong branch — over the 26 distinct values of this field under
   * `output/` the two glosses produce zero differences, because every corpus occurrence there
   * arrives as the `data corpus` compound, which resolves ABOVE the fork. So swapping this
   * `$derived` to `buyerFacingResearchProse` left the whole suite green.
   *
   * A BARE `corpus` separates them: this field is prose about the ideas, so its corpus is the
   * DATASET a product would have to build ("the recipe dataset"), never the run's own
   * collected evidence. Asserted through the RENDER, because the fork happens in the
   * component — a unit test on the function could not have caught a mis-wired `$derived`.
   */
  it("does not render unbound portfolio vocabulary on the selection surface", async () => {
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        ideaPortfolioSummary:
          "Alpha Idea already owns its inputs; Beta Idea still lacks the recipe corpus.",
      },
    });

    const take = await view.findByLabelText("Discovery take");
    expect(take).toHaveTextContent("stored recommendation is not bound to exact current idea revisions");
    expect(take).not.toHaveTextContent("recipe dataset");
    expect(take).not.toHaveTextContent("collected evidence");
  });
});

describe("SelectionWorkbench — stable selection identity", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chatLedger.reset();
    chatPanel.dock();
    vi.mocked(getChatHistory).mockResolvedValue({ messages: [], weakPool: false } as never);
  });

  afterEach(cleanup);

  it("opens the exact revision of the deterministic strongest eligible candidate", async () => {
    vi.mocked(getSelectionDecisionState).mockResolvedValueOnce({
      schemaVersion: 1,
      jobId: "job-1",
      status: "AWAITING_SELECTION",
      shortlist: { version: 0, items: [] },
      profile: null,
      founderFit: null,
      challenges: [],
      ownerEvidence: [],
      assumptions: [],
      experiments: [],
      conclusions: [],
      staleCounts: { shortlist: 0, profile: 0, founderFit: 0, challenges: 0, ownerEvidence: 0, assumptions: 0, experiments: 0, conclusions: 0, total: 0 },
      deepResearch: { eligible: false, optionalWorkRequired: false, blockers: ["NO_CURRENT_SHORTLIST"] },
      nextAction: {
        kind: "select_candidate",
        target: "shortlist",
        reason: "Review the first stored candidate.",
        required: true,
        ideas: [{ ideaId: "idea-a", ideaRevision: 1, title: "Audience-led path" }],
        lens: null,
        records: [],
      },
    } as never);
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: [
          solution("Alpha", { idea_id: "idea-a", idea_revision: 1, headline: "Audience-led path", adjusted_composite_score: 0.5 }),
          solution("Beta", { idea_id: "idea-b", idea_revision: 2, headline: "Workflow-led path", adjusted_composite_score: 0.7 }),
        ],
      },
    });

    await fireEvent.click(await view.findByRole("button", { name: "Review Workflow-led path" }));
    expect(await view.findByRole("dialog", { name: "Solution details: Workflow-led path" })).toBeInTheDocument();
  });

  it("keeps a raw typed gap-only kill eligible for the strongest-candidate action", async () => {
    vi.mocked(getSelectionDecisionState).mockResolvedValueOnce({
      schemaVersion: 1,
      jobId: "job-1",
      status: "AWAITING_SELECTION",
      shortlist: { version: 0, items: [] },
      profile: null,
      founderFit: null,
      challenges: [],
      ownerEvidence: [],
      assumptions: [],
      experiments: [],
      conclusions: [],
      staleCounts: { shortlist: 0, profile: 0, founderFit: 0, challenges: 0, ownerEvidence: 0, assumptions: 0, experiments: 0, conclusions: 0, total: 0 },
      deepResearch: { eligible: false, optionalWorkRequired: false, blockers: ["NO_CURRENT_SHORTLIST"] },
      nextAction: {
        kind: "select_candidate",
        target: "shortlist",
        reason: "Review the strongest eligible candidate.",
        required: true,
        ideas: [],
        lens: null,
        records: [],
      },
    } as never);
    const gapLeader = solution("Gap leader", {
      idea_id: "idea-gap",
      idea_revision: 1,
      headline: "Gap-only high score",
      adjusted_composite_score: 0.8,
      red_team_verdict: "killed",
      red_team_findings: [{
        claim: "The review did not establish a reachable payer.",
        kind: "evidence_gap",
      }],
    });
    const survivor = solution("Survivor", {
      idea_id: "idea-survivor",
      idea_revision: 1,
      adjusted_composite_score: 0.6,
    });
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, solutions: [gapLeader, survivor] },
    });

    expect(await view.findByRole("button", { name: "Review Gap-only high score" }))
      .toBeInTheDocument();
    const row = within(view.getByRole("table", { name: "Ranked ideas" }))
      .getAllByRole("row")
      .find((entry) => entry.textContent?.includes("Gap-only high score")) as HTMLElement;
    expect(row).toHaveTextContent("Evidence incomplete");
    expect(row).not.toHaveTextContent("Premise unproven");
  });

  it("keeps candidates with the same stored name independently selectable", async () => {
    const duplicateNames = [
      solution("Shared internal name", { idea_id: "idea-a", headline: "Audience-led path" }),
      solution("Shared internal name", { idea_id: "idea-b", headline: "Workflow-led path" }),
    ];
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, solutions: duplicateNames },
    });

    const audience = view.getByLabelText("Select Audience-led path") as HTMLInputElement;
    const workflow = view.getByLabelText("Select Workflow-led path") as HTMLInputElement;
    await fireEvent.click(audience);
    await fireEvent.click(workflow);

    expect(audience.checked).toBe(true);
    expect(workflow.checked).toBe(true);
    expect(view.getByRole("complementary", { name: "Ideas for Deep Research" })).toHaveAccessibleName("Ideas for Deep Research");
    expect(view.getByLabelText("2 of 3 ideas selected")).toBeInTheDocument();

    await fireEvent.click(audience);
    expect(audience.checked).toBe(false);
    expect(workflow.checked).toBe(true);
    expect(view.getByText("Check the evidence")).toBeInTheDocument();
  });

  it("routes legacy alternatives links to one exact selected candidate", async () => {
    const identified = [
      solution("Alpha Idea", { idea_id: "idea-alpha" }),
      solution("Beta Idea", { idea_id: "idea-beta" }),
    ];
    page.url = new URL("http://localhost/jobs/job-1?selectionTool=alternatives") as typeof page.url;
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, solutions: identified, selectedSolutionIds: ["idea-alpha"] },
    });

    await waitFor(() => expect(goto).toHaveBeenCalledWith(
      "/jobs/job-1/selection/compare?idea=idea-alpha%3A1&tool=variants",
      { replaceState: true },
    ));
    expect(view.queryByRole("heading", { name: "Branch a new direction" })).not.toBeInTheDocument();
    expect(seedIdea).not.toHaveBeenCalled();
  });

  it("routes an analyst-prepared directions brief with exact current revisions without generating", async () => {
    const identified = [
      solution("Alpha Idea", { idea_id: "idea-alpha", idea_revision: 2 }),
      solution("Beta Idea", { idea_id: "idea-beta", idea_revision: 4 }),
    ];
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [{
        id: "asst-concept-brief",
        gateStage: 5,
        role: "assistant",
        content: "I prepared a shaping question for review.",
        patchJson: {
          kind: "selection_copilot_action",
          action: "prefill",
          target: "concept_forge",
          ideas: [
            { ideaId: "idea-beta", ideaRevision: 4, solutionName: "Beta Idea" },
            { ideaId: "idea-alpha", ideaRevision: 2, solutionName: "Alpha Idea" },
          ],
          values: {
            purpose: "resolve_tradeoff",
            targetTradeoff: "Faster launch versus a stronger evidence moat",
          },
          rationale: "Compare the two viable shapes before evaluating either one.",
          caveats: ["The generated branches still need fresh evaluation."],
        },
        suggestionsJson: null,
        truncated: false,
        createdAt: "2026-07-16T00:00:00.000Z",
      }],
      weakPool: false,
    } as never);
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, solutions: identified },
    });

    await fireEvent.click(await view.findByRole("button", { name: "Review directions brief" }));

    await waitFor(() => expect(goto).toHaveBeenCalledWith(
      "/jobs/job-1/selection/compare?idea=idea-beta%3A4&idea=idea-alpha%3A2&tool=variants&mode=resolve_tradeoff",
      expect.objectContaining({
        state: expect.objectContaining({
          selectionConceptPrefill: expect.objectContaining({
            requestId: "asst-concept-brief",
            purpose: "resolve_tradeoff",
            targetTradeoff: "Faster launch versus a stronger evidence moat",
          }),
          selectionToolOrigin: {
            tool: "variants",
            jobId: "job-1",
            returnHref: "/jobs/job-1",
            historyOwned: true,
          },
        }),
      }),
    ));
    expect(getSelectionConceptSets).not.toHaveBeenCalled();
    expect(seedIdea).not.toHaveBeenCalled();
  });

  it("routes one selected idea to the canonical shaping workspace without sending or changing it", async () => {
    chatPanel.close();
    const identified = [
      solution("Alpha Idea", { idea_id: "idea-alpha" }),
      solution("Beta Idea", { idea_id: "idea-beta" }),
    ];
    page.url = new URL("http://localhost/jobs/job-1?selectionTool=alternatives") as typeof page.url;
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, solutions: identified, selectedSolutionIds: ["idea-alpha"] },
    });

    const alpha = view.getByLabelText("Deselect Alpha Idea") as HTMLInputElement;

    await waitFor(() => expect(goto).toHaveBeenCalledWith(
      "/jobs/job-1/selection/compare?idea=idea-alpha%3A1&tool=variants",
      { replaceState: true },
    ));
    expect(alpha.checked).toBe(true);
    expect(streamChat).not.toHaveBeenCalled();
    expect(seedIdea).not.toHaveBeenCalled();
  });

  it("routes two exact candidates to the shared shaping workspace without changing the shortlist", async () => {
    chatPanel.close();
    const identified = [
      solution("Alpha Idea", { idea_id: "idea-alpha" }),
      solution("Beta Idea", { idea_id: "idea-beta" }),
    ];
    page.url = new URL("http://localhost/jobs/job-1?selectionTool=alternatives") as typeof page.url;
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, solutions: identified, selectedSolutionIds: ["idea-alpha", "idea-beta"] },
    });

    const alpha = view.getByLabelText("Deselect Alpha Idea") as HTMLInputElement;
    const beta = view.getByLabelText("Deselect Beta Idea") as HTMLInputElement;

    await waitFor(() => expect(goto).toHaveBeenCalledWith(
      "/jobs/job-1/selection/compare?idea=idea-alpha%3A1&idea=idea-beta%3A1&tool=variants",
      { replaceState: true },
    ));
    expect(alpha.checked).toBe(true);
    expect(beta.checked).toBe(true);
    expect(streamChat).not.toHaveBeenCalled();
    expect(seedIdea).not.toHaveBeenCalled();
  });

  it("restores a persisted selection by idea ID", async () => {
    const identified = [
      solution("Alpha Idea", { idea_id: "idea-alpha" }),
      solution("Beta Idea", { idea_id: "idea-beta" }),
    ];
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: identified,
        selectedSolutions: ["Alpha Idea"],
        selectedSolutionIds: ["idea-beta"],
      },
    });

    const alpha = view.getByLabelText("Select Alpha Idea") as HTMLInputElement;
    const beta = view.getByLabelText("Deselect Beta Idea") as HTMLInputElement;
    await waitFor(() => expect(beta.checked).toBe(true));
    expect(alpha.checked).toBe(false);
  });

  it("opens an exact candidate revision in a shareable detail tab", async () => {
    page.url = new URL(
      `http://localhost/jobs/job-1?keep=1&detailTab=detail&ideaId=idea-b&ideaRevision=4#${RANKED_IDEAS_ANCHOR}`,
    ) as typeof page.url;
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: [
          solution("Same name", {
            idea_id: "idea-a",
            idea_revision: 2,
            headline: "Earlier candidate",
            description: "Earlier-revision description",
          }),
          solution("Same name", {
            idea_id: "idea-b",
            idea_revision: 4,
            headline: "Exact shared candidate",
            description: "Exact-revision description",
          }),
        ],
      },
    });

    const detail = await view.findByRole("dialog", {
      name: "Solution details: Exact shared candidate",
    });
    expect(detail).toBeInTheDocument();
    expect(view.getByRole("tab", { name: "All details" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(within(detail).getByText("Exact-revision description")).toBeInTheDocument();
    expect(within(detail).queryByText("Earlier-revision description")).not.toBeInTheDocument();
  });

  it("opens a deep-linked idea whose ranked pool arrives after mount", async () => {
    // REGRESSION: the link resolved once, against an empty pool, reported itself dead
    // and consumed the query — so it stayed dead when the ideas landed a tick later.
    page.url = new URL(
      "http://localhost/jobs/job-1?detailTab=detail&ideaId=idea-beta&ideaRevision=1",
    ) as typeof page.url;
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, solutions: [] },
    });
    expect(view.queryByRole("dialog")).toBeNull();

    await view.rerender({
      ...baseProps,
      solutions: [
        solution("Alpha Idea", { idea_id: "idea-alpha", headline: "Alpha headline" }),
        solution("Beta Idea", { idea_id: "idea-beta", headline: "Beta headline" }),
      ],
    });

    await view.findByRole("dialog", { name: "Solution details: Beta headline" });
  });

  it("keeps a clicked idea open when the URL still names a different one", async () => {
    // SHIP BLOCKER: shallow navigation does not always land (it throws before the router
    // initialises), leaving the previous idea's ideaId in the address bar. The URL-sync
    // effect then re-resolved it on the next pool change and swapped one idea's body in
    // under another's title — on the screen whose next click spends 100 credits.
    page.url = new URL(
      "http://localhost/jobs/job-1?detailTab=overview&ideaId=idea-alpha&ideaRevision=1",
    ) as typeof page.url;
    const solutions = [
      solution("Alpha Idea", { idea_id: "idea-alpha", headline: "Alpha headline" }),
      solution("Beta Idea", { idea_id: "idea-beta", headline: "Beta headline" }),
      solution("Gamma Idea", { idea_id: "idea-gamma", headline: "Gamma headline" }),
    ];
    const view = render(SelectionWorkbench, { props: { ...baseProps, solutions } });

    // The deep link opens Alpha, as asked.
    await view.findByRole("dialog", { name: "Solution details: Alpha headline" });
    await fireEvent.click(view.getByRole("button", { name: "Close details" }));

    // pushState is mocked here, so `page.url` keeps the stale ideaId — exactly the state
    // the failed-navigation path leaves behind in the browser.
    vi.mocked(pushState).mockImplementationOnce(() => {
      throw new Error("Cannot call pushState(...) before router is initialized");
    });
    await fireEvent.click(
      view.getByRole("button", { name: /^Review details for Gamma headline/ }),
    );
    await view.findByRole("dialog", { name: "Solution details: Gamma headline" });

    // A batch lands: the pool changes under an unchanged (stale) URL.
    await view.rerender({
      ...baseProps,
      solutions: [
        ...solutions,
        solution("Delta Idea", { idea_id: "idea-delta", headline: "Delta headline" }),
      ],
    });

    // Still the idea the user clicked, not the one the address bar names.
    await view.findByRole("dialog", { name: "Solution details: Gamma headline" });
    expect(view.queryByRole("dialog", { name: "Solution details: Alpha headline" }))
      .toBeNull();
  });

  it("returns focus to the last paged candidate when URL-driven details close", async () => {
    page.url = new URL(
      "http://localhost/jobs/job-1?detailTab=overview&ideaId=idea-beta&ideaRevision=2",
    ) as typeof page.url;
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: [
          solution("Alpha Idea", { idea_id: "idea-alpha", idea_revision: 1 }),
          solution("Beta Idea", { idea_id: "idea-beta", idea_revision: 2 }),
          solution("Gamma Idea", { idea_id: "idea-gamma", idea_revision: 3 }),
        ],
      },
    });

    await view.findByRole("dialog", { name: "Solution details: Beta Idea" });
    await fireEvent.click(view.getByRole("button", { name: "Next idea" }));
    await view.findByRole("dialog", { name: "Solution details: Gamma Idea" });
    await fireEvent.click(view.getByRole("button", { name: "Close details" }));

    const gammaTrigger = view.getByRole("button", { name: /^Review details for Gamma Idea/ });
    await waitFor(() => expect(gammaTrigger).toHaveFocus());
  });

  it("preserves unrelated query state while opening and closing exact details", async () => {
    page.url = new URL(`http://localhost/jobs/job-1?keep=1#${RANKED_IDEAS_ANCHOR}`) as typeof page.url;
    const back = vi.spyOn(window.history, "back").mockImplementation(() => undefined);
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: [
          solution("Alpha Idea", {
            idea_id: "idea-alpha",
            idea_revision: 3,
          }),
        ],
      },
    });

    await fireEvent.click(
      view.getByRole("button", { name: /^Review details for Alpha Idea/ }),
    );
    const openedUrl = new URL(
      vi.mocked(pushState).mock.calls.at(-1)?.[0] as string,
      "http://localhost",
    );
    expect(openedUrl.searchParams.get("keep")).toBe("1");
    expect(openedUrl.searchParams.get("ideaId")).toBe("idea-alpha");
    expect(openedUrl.searchParams.get("ideaRevision")).toBe("3");
    expect(openedUrl.searchParams.get("detailTab")).toBe("overview");
    expect(openedUrl.hash).toBe(`#${RANKED_IDEAS_ANCHOR}`);

    await fireEvent.click(view.getByRole("tab", { name: "All details" }));
    const tabUrl = new URL(
      vi.mocked(replaceState).mock.calls.at(-1)?.[0] as string,
      "http://localhost",
    );
    expect(tabUrl.searchParams.get("keep")).toBe("1");
    expect(tabUrl.searchParams.get("ideaId")).toBe("idea-alpha");
    expect(tabUrl.searchParams.get("ideaRevision")).toBe("3");
    expect(tabUrl.searchParams.get("detailTab")).toBe("detail");

    await fireEvent.click(view.getByRole("button", { name: "Close details" }));
    expect(back).toHaveBeenCalledOnce();
    back.mockRestore();
  });

  it("closes idea details, expands the requested Discovery evidence, and preserves unrelated URL state", async () => {
    page.url = new URL("http://localhost/jobs/job-1?keep=1") as typeof page.url;
    const back = vi.spyOn(window.history, "back").mockImplementation(() => undefined);
    const scrollIntoView = vi.fn();
    const evidenceSection = document.createElement("section");
    evidenceSection.id = "pain-points";
    Object.defineProperty(evidenceSection, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });
    const evidenceTrigger = document.createElement("button");
    evidenceTrigger.textContent = "Pain Points";
    evidenceTrigger.setAttribute("aria-expanded", "false");
    evidenceTrigger.setAttribute("aria-controls", "pain-points-content");
    evidenceTrigger.addEventListener("click", () => {
      evidenceTrigger.setAttribute("aria-expanded", "true");
    });
    evidenceSection.append(evidenceTrigger);
    document.body.append(evidenceSection);

    try {
      const view = render(SelectionWorkbench, {
        props: {
          ...baseProps,
          painPointCount: 2,
          solutions: [
            solution("Alpha Idea", {
              idea_id: "idea-alpha",
              idea_revision: 3,
            }),
          ],
        },
      });

      await fireEvent.click(
        view.getByRole("button", { name: /^Review details for Alpha Idea/ }),
      );
      await fireEvent.click(view.getByRole("link", { name: "Pain evidence" }));

      await waitFor(() => expect(view.queryByRole("dialog")).not.toBeInTheDocument());
      expect(back).not.toHaveBeenCalled();
      expect(evidenceTrigger).toHaveAttribute("aria-expanded", "true");
      expect(scrollIntoView).toHaveBeenCalledWith({
        behavior: expect.any(String),
        block: "start",
      });
      expect(evidenceTrigger).toHaveFocus();

      const evidenceUrl = new URL(
        vi.mocked(replaceState).mock.calls.at(-1)?.[0] as string,
        "http://localhost",
      );
      expect(evidenceUrl.searchParams.get("keep")).toBe("1");
      expect(evidenceUrl.searchParams.has("detailTab")).toBe(false);
      expect(evidenceUrl.searchParams.has("ideaId")).toBe(false);
      expect(evidenceUrl.hash).toBe("#pain-points");
    } finally {
      evidenceSection.remove();
      back.mockRestore();
    }
  });

  it("shows a recoverable error for a stale exact-revision link", async () => {
    page.url = new URL(
      "http://localhost/jobs/job-1?keep=1&detailTab=overview&ideaId=idea-a&ideaRevision=9",
    ) as typeof page.url;
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: [
          solution("Alpha Idea", {
            idea_id: "idea-a",
            idea_revision: 2,
          }),
        ],
      },
    });

    expect(
      await view.findByRole("alert"),
    ).toHaveTextContent("That exact idea revision is no longer available");
    expect(view.queryByRole("dialog")).not.toBeInTheDocument();

    await fireEvent.click(view.getByRole("button", { name: "Return to ranked ideas" }));
    const cleanedUrl = new URL(
      vi.mocked(replaceState).mock.calls.at(-1)?.[0] as string,
      "http://localhost",
    );
    expect(cleanedUrl.searchParams.get("keep")).toBe("1");
    expect(cleanedUrl.searchParams.has("detailTab")).toBe(false);
    expect(cleanedUrl.searchParams.has("ideaId")).toBe(false);
    expect(cleanedUrl.searchParams.has("ideaRevision")).toBe(false);
  });

  it("says so when a deep-linked evaluation is not in this report", async () => {
    // `selectError` was WRITE-ONLY: declared, assigned by reviewEvaluationResult (and by
    // the stale-shortlist-proposal path), and rendered nowhere — so an ?evaluationId=
    // that matched no ruled-out record consumed the query, opened nothing, and said
    // nothing. A dead deep link has to be visible, not silent.
    page.url = new URL(
      "http://localhost/jobs/job-1?evaluationId=cmdispatch-missing",
    ) as typeof page.url;
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, examinedRuledOut: [] },
    });

    await waitFor(() => expect(
      view.getByText("That evaluated result is no longer available in this report."),
    ).toBeInTheDocument());
    expect(view.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("joins the seed deep-link contract: ?evaluationId=<dispatch id> opens a plain-seed finding carrying dispatch_id only", async () => {
    // The two halves of the flagship seed link were only ever pinned APART: ChatThread
    // emits `?evaluationId=<JobDispatch.id>` (producer) and the workbench resolves it
    // against `finding.dispatch_id` (consumer). Nothing joined them, so renaming either
    // carrier left every test green and the link dead — which is how this broke twice.
    //
    // A PLAIN seed is the only shape that exercises the join: `withIdentity` never
    // stamps `evaluation_id` (only `stampSynthesizedIdeaIdentity` does), so `dispatch_id`
    // is the sole carrier and the `evaluation_id` disjunct cannot mask a regression.
    page.url = new URL(
      "http://localhost/jobs/job-1?evaluationId=cmdispatch77",
    ) as typeof page.url;
    const plainSeedFinding: RuledOutFinding = {
      pain_title: "Chasing late invoices",
      idea_name: "InvoiceChaser",
      source_frame: "user_seed",
      reason: "Thin market signal",
      market_fit: 0.2,
      market_fit_band: "low",
      prior_tier: "winner",
      source: "demoted_winner",
      evidence: "Only a handful of mentions",
      dispatch_id: "cmdispatch77",
    };

    const view = render(SelectionWorkbench, {
      props: { ...baseProps, examinedRuledOut: [plainSeedFinding] },
    });

    expect(
      await view.findByRole("button", { name: "Close ruled-out analysis" }),
    ).toBeInTheDocument();
    expect(
      view.queryByText("That evaluated result is no longer available in this report."),
    ).not.toBeInTheDocument();

    // Negative control: identical shape, a dispatch id from some other evaluation.
    // Without it the positive half could pass on a match-everything consumer.
    cleanup();
    const other = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        examinedRuledOut: [{ ...plainSeedFinding, dispatch_id: "cmOTHER" }],
      },
    });

    await waitFor(() => expect(
      other.getByText("That evaluated result is no longer available in this report."),
    ).toBeInTheDocument());
    expect(
      other.queryByRole("button", { name: "Close ruled-out analysis" }),
    ).not.toBeInTheDocument();
  });

  it("lets a dead evaluation deep link be dismissed instead of pinning it for the session", async () => {
    // `selectError` had no clear at all — unlike `detailUrlError`/`clearDetailUrlError` —
    // so one dead deep link parked the message above the pool for the component's life.
    page.url = new URL(
      "http://localhost/jobs/job-1?evaluationId=cmdispatch-missing",
    ) as typeof page.url;
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, examinedRuledOut: [] },
    });

    await waitFor(() => expect(
      view.getByText("That evaluated result is no longer available in this report."),
    ).toBeInTheDocument());

    await fireEvent.click(view.getByRole("button", { name: "Dismiss" }));

    expect(
      view.queryByText("That evaluated result is no longer available in this report."),
    ).not.toBeInTheDocument();
  });
});

describe("SelectionWorkbench — durable shortlist draft", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chatLedger.reset();
    chatPanel.close();
    vi.mocked(getChatHistory).mockResolvedValue({ messages: [], weakPool: false } as never);
  });

  afterEach(cleanup);

  it("restores the authoritative exact-revision draft before legacy final fields", async () => {
    const identified = [
      solution("Same name", { idea_id: "idea-a", idea_revision: 1, headline: "First revision" }),
      solution("Same name", { idea_id: "idea-b", idea_revision: 2, headline: "Second revision" }),
    ];
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: identified,
        selectedSolutionIds: ["idea-a"],
        selectionDraft: {
          version: 4,
          items: [{ ideaId: "idea-b", ideaRevision: 2 }],
        },
      },
    });

    const first = view.getByLabelText("Select First revision") as HTMLInputElement;
    const second = view.getByLabelText("Deselect Second revision") as HTMLInputElement;
    await waitFor(() => expect(second.checked).toBe(true));
    expect(first.checked).toBe(false);
  });

  it("opens the stable saved-shortlist review route without ad-hoc idea query state", async () => {
    const identified = [
      solution("Alpha Idea", { idea_id: "idea-alpha", idea_revision: 3 }),
      solution("Beta Idea", { idea_id: "idea-beta", idea_revision: 2 }),
    ];
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: identified,
        selectionDraft: {
          version: 7,
          items: [
            { ideaId: "idea-alpha", ideaRevision: 3 },
            { ideaId: "idea-beta", ideaRevision: 2 },
          ],
        },
      },
    });

    await fireEvent.click(await view.findByRole("button", { name: "Review and start" }));

    expect(goto).toHaveBeenCalledWith("/jobs/job-1/selection/review");
  });

  it("autosaves the full exact-revision shortlist and confirms it inline", async () => {
    const identified = [solution("Alpha Idea", { idea_id: "idea-alpha", idea_revision: 3 })];
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: identified,
        selectionDraft: { version: 7, items: [] },
      },
    });

    await fireEvent.click(view.getByLabelText("Select Alpha Idea"));

    await waitFor(() => expect(saveSelectionDraft).toHaveBeenCalledWith(
      "job-1",
      7,
      [{ ideaId: "idea-alpha", ideaRevision: 3 }],
    ));
    expect(await view.findByText("Shortlist saved")).toBeInTheDocument();
  });

  it("blocks paid pool mutations until shortlist autosave settles", async () => {
    let settleSave: (() => void) | undefined;
    const identified = [solution("Alpha Idea", { idea_id: "idea-alpha", idea_revision: 3 })];
    vi.mocked(saveSelectionDraft).mockImplementationOnce((_jobId, expectedVersion, items) => (
      new Promise((resolve) => {
        settleSave = () => resolve({ version: expectedVersion + 1, items });
      })
    ));
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: identified,
        selectionDraft: { version: 7, items: [] },
      },
    });

    await fireEvent.click(view.getByLabelText("Select Alpha Idea"));
    await waitFor(() => expect(saveSelectionDraft).toHaveBeenCalledTimes(1));

    expect(view.getByRole("button", { name: "Add another batch" })).toBeDisabled();
    expect(view.getByRole("button", { name: /Branch a new direction/ })).toBeDisabled();

    settleSave?.();
    await waitFor(() => {
      expect(view.getByRole("button", { name: "Add another batch" })).not.toBeDisabled();
      expect(view.getByRole("button", { name: /Branch a new direction/ })).not.toBeDisabled();
    });
  });

  it("consumes an exact routed proposal without mutating until the owner applies it", async () => {
    const identified = [
      solution("Alpha Idea", { idea_id: "idea-alpha", idea_revision: 3 }),
      solution("Beta Idea", { idea_id: "idea-beta", idea_revision: 2 }),
    ];
    page.state = {
      shortlistProposal: {
        requestId: "proposal-1",
        expectedVersion: 7,
        refs: [{ ideaId: "idea-beta", ideaRevision: 2 }],
        returnHref: "/jobs/job-1/selection/compare?idea=idea-beta%3A2",
        reason: "compare_scope",
      },
    } as typeof page.state;

    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: identified,
        selectionDraft: {
          version: 7,
          items: [{ ideaId: "idea-alpha", ideaRevision: 3 }],
        },
      },
    });

    expect(await view.findByRole("dialog", { name: "Review shortlist changes" })).toBeInTheDocument();
    expect(view.getByText("Proposed shortlist")).toBeInTheDocument();
    expect(saveSelectionDraft).not.toHaveBeenCalled();

    await fireEvent.click(view.getByRole("button", { name: "Apply shortlist" }));
    await waitFor(() => expect(saveSelectionDraft).toHaveBeenCalledWith(
      "job-1",
      7,
      [{ ideaId: "idea-beta", ideaRevision: 2 }],
    ));
  });

  it("keeps a failed save visible and retries without losing the local pick", async () => {
    vi.mocked(saveSelectionDraft).mockRejectedValueOnce(new Error("Connection failed"));
    const identified = [solution("Alpha Idea", { idea_id: "idea-alpha", idea_revision: 1 })];
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, solutions: identified, selectionDraft: { version: 2, items: [] } },
    });

    const alpha = view.getByLabelText("Select Alpha Idea") as HTMLInputElement;
    await fireEvent.click(alpha);
    await view.findByText("Connection failed");
    expect(alpha.checked).toBe(true);

    await fireEvent.click(view.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(saveSelectionDraft).toHaveBeenCalledTimes(2));
    expect(await view.findByText("Shortlist saved")).toBeInTheDocument();
  });

  it("asks for a reload when another session wins the version race", async () => {
    vi.mocked(saveSelectionDraft).mockRejectedValueOnce(
      new ApiError("The shortlist changed in another session", 409, {
        code: "SELECTION_DRAFT_CONFLICT",
      }),
    );
    const identified = [solution("Alpha Idea", { idea_id: "idea-alpha", idea_revision: 1 })];
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, solutions: identified, selectionDraft: { version: 2, items: [] } },
    });

    await fireEvent.click(view.getByLabelText("Select Alpha Idea"));

    expect(await view.findByText("The shortlist changed in another session")).toBeInTheDocument();
    expect(view.getByRole("button", { name: "Reload" })).toBeInTheDocument();
  });
});

describe("SelectionWorkbench — similar candidate families", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chatLedger.reset();
    chatPanel.close();
    vi.mocked(getChatHistory).mockResolvedValue({ messages: [], weakPool: false } as never);
  });

  afterEach(cleanup);

  it("keeps a selected-family advisory in document flow before the candidate table", async () => {
    const identified = [
      solution("Alpha Idea", { idea_id: "idea-alpha", headline: "Audience-led monitor" }),
      solution("Beta Idea", { idea_id: "idea-beta", headline: "Workflow-led monitor" }),
    ];
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: identified,
        selectedSolutionIds: ["idea-alpha", "idea-beta"],
        overlapGroups: [{
          idea_names: ["Alpha Idea", "Beta Idea"],
          shared_product: "Market signal monitor",
        }],
      },
    });

    const notice = await view.findByLabelText("Shortlist overlap");
    const table = view.getByRole("table", { name: "Ranked ideas" });
    expect(notice).toHaveTextContent(
      "Audience-led monitor and Workflow-led monitor are variants of the same product (Market signal monitor).",
    );
    expect(
      notice.compareDocumentPosition(table) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("routes an exact overlap family to the canonical comparison without changing the shortlist", async () => {
    const identified = [
      solution("Alpha Idea", { idea_id: "idea-alpha", headline: "Audience-led monitor" }),
      solution("Beta Idea", { idea_id: "idea-beta", headline: "Workflow-led monitor" }),
      solution("Gamma Idea", { idea_id: "idea-gamma" }),
    ];
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: identified,
        overlapGroups: [{
          idea_names: ["Alpha Idea", "Beta Idea"],
          shared_product: "Market signal monitor",
        }],
      },
    });
    await openAppendix(view);

    const alpha = view.getByLabelText("Select Audience-led monitor") as HTMLInputElement;
    const beta = view.getByLabelText("Select Workflow-led monitor") as HTMLInputElement;
    expect(alpha.checked).toBe(false);
    expect(beta.checked).toBe(false);
    expect(view.getByText("Similar idea family · 2")).toBeInTheDocument();
    expect(view.getByText("Market signal monitor")).toBeInTheDocument();

    await fireEvent.click(view.getByRole("button", { name: "Compare variants" }));

    expect(goto).toHaveBeenCalledWith(
      "/jobs/job-1/selection/compare?idea=idea-alpha%3A1&idea=idea-beta%3A1&view=market",
    );
    expect(alpha.checked).toBe(false);
    expect(beta.checked).toBe(false);
  });

  it("keeps comparison available when the shortlist is full without mutating it", async () => {
    const ideas = [
      solution("Alpha Idea", { idea_id: "idea-alpha", headline: "Audience-led monitor" }),
      solution("Beta Idea", { idea_id: "idea-beta", headline: "Workflow-led monitor" }),
      solution("Gamma Idea", { idea_id: "idea-gamma" }),
      solution("Delta Idea", { idea_id: "idea-delta" }),
      solution("Epsilon Idea", { idea_id: "idea-epsilon" }),
    ];
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: ideas,
        selectedSolutionIds: ["idea-gamma", "idea-delta", "idea-epsilon"],
        overlapGroups: [{
          idea_names: ["Alpha Idea", "Beta Idea"],
          shared_product: "Market signal monitor",
        }],
      },
    });
    await waitFor(() => expect(
      (view.getByLabelText("Deselect Gamma Idea") as HTMLInputElement).checked,
    ).toBe(true));
    await openAppendix(view);

    await fireEvent.click(view.getByRole("button", { name: "Compare variants" }));

    expect(goto).toHaveBeenCalledWith(
      "/jobs/job-1/selection/compare?idea=idea-alpha%3A1&idea=idea-beta%3A1&view=market",
    );
    expect((view.getByLabelText("Deselect Gamma Idea") as HTMLInputElement).checked).toBe(true);
    expect((view.getByLabelText("Deselect Delta Idea") as HTMLInputElement).checked).toBe(true);
    expect((view.getByLabelText("Deselect Epsilon Idea") as HTMLInputElement).checked).toBe(true);
  });

  it("does not guess when legacy overlap names map to multiple exact ideas", async () => {
    const duplicates = [
      solution("Shared name", { idea_id: "idea-a", headline: "Audience path" }),
      solution("Shared name", { idea_id: "idea-b", headline: "Workflow path" }),
    ];
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: duplicates,
        overlapGroups: [{
          idea_names: ["Shared name", "Shared name"],
          shared_product: "Ambiguous legacy family",
        }],
      },
    });
    await openAppendix(view);

    expect(view.queryByRole("button", { name: "Compare variants" })).not.toBeInTheDocument();
    expect(view.getByText("Shortlist 2-3 to compare")).toBeInTheDocument();
  });
});

describe("SelectionWorkbench — shared workspace overlay", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chatLedger.reset();
    chatPanel.dock();
    vi.mocked(getChatHistory).mockResolvedValue({ messages: [], weakPool: false } as never);
  });

  afterEach(() => {
    cleanup();
  });

  it("does not mount owner experiment planning in shared mode", () => {
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, interactive: false },
    });

    expect(view.queryByRole("heading", { name: "Test what could change the decision" })).not.toBeInTheDocument();
    expect(view.queryByRole("heading", { name: "Choose the next useful step" })).not.toBeInTheDocument();
    expect(view.queryByRole("button", { name: /^Shape/ })).not.toBeInTheDocument();
    expect(getSelectionExperiments).not.toHaveBeenCalled();
    expect(getSelectionConceptSets).not.toHaveBeenCalled();
  });

  it("returns to the expanded chat after closing an idea opened from chat", async () => {
    chatPanel.expand();
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [{
        id: "chat-idea-return",
        gateStage: 5,
        role: "assistant",
        content: "Open ProMatchDesk for the full evaluation.",
        patchJson: null,
        suggestionsJson: null,
        truncated: false,
        createdAt: "1",
      }],
      weakPool: false,
    } as never);
    const proMatchDesk = solution("ProMatchDesk (CS2+Dota 2)");
    const { findByLabelText, findByRole } = render(SelectionWorkbench, {
      props: { ...baseProps, solutions: [proMatchDesk] },
    });

    await findByRole("dialog", { name: "Analyst conversation" });
    await fireEvent.click(await findByRole(
      "button", { name: /^ProMatchDesk \(CS2\+Dota 2\) ?, open details$/ },
    ));
    await findByRole("dialog", { name: "Solution details: ProMatchDesk (CS2+Dota 2)" });
    expect(chatPanel.state).toBe("launcher");

    await fireEvent.click(await findByLabelText("Close details"));
    await waitFor(() => expect(chatPanel.state).toBe("expanded"));
    await findByRole("dialog", { name: "Analyst conversation" });
  });

  it("uses the same modal shell for idea detail and expanded chat", async () => {
    const { findByLabelText, findByRole } = render(SelectionWorkbench, { props: baseProps });

    await fireEvent.click(await findByRole("button", { name: /^Review details for Alpha Idea/ }));
    const ideaDialog = await findByRole("dialog", { name: "Solution details: Alpha Idea" });
    const ideaOverlay = ideaDialog.closest('[data-workspace-overlay="modal"]');
    expect(ideaOverlay).not.toBeNull();
    expect(ideaOverlay).toHaveAttribute("data-workspace-overlay-size", "standard");

    await fireEvent.click(await findByLabelText("Close details"));
    await fireEvent.click(await findByLabelText("Read the conversation full width"));
    const chatDialog = await findByRole("dialog", { name: "Analyst conversation" });
    const chatOverlay = chatDialog.closest('[data-workspace-overlay="modal"]');
    expect(chatOverlay).not.toBeNull();
    expect(chatOverlay).toHaveAttribute("data-workspace-overlay-size", "wide");
  });
});

describe("SelectionWorkbench — accepted narrowed variant", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chatLedger.reset();
    chatPanel.open();
    vi.mocked(getChatHistory).mockResolvedValue({ messages: [], weakPool: false } as never);
  });

  afterEach(cleanup);

  it("routes an exact parent revision into the canonical test workspace", async () => {
    chatPanel.close();
    const parent = solution("Signal Desk", {
      idea_id: "idea-parent",
      idea_revision: 3,
    });
    const child = solution("Agency Renewal Signal Desk", {
      idea_id: "idea-child",
      idea_revision: 1,
      synthesis_operation: "narrow",
      synthesis_source_message_id: "proposal-message-1",
      synthesized_from: [{
        idea_id: "idea-parent",
        idea_revision: 3,
        solution_name: "Signal Desk",
        contribution: "Keep the recurring signal workflow.",
      }],
    });
    const experiment = {
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
    const synthesisPatch = {
      kind: "idea_synthesis",
      operation: "narrow",
      proposedTitle: child.solution_name,
      proposedBrief: "A focused signal desk for agency renewal reviews.",
      changeSummary: "Narrows the buyer and workflow.",
      rationale: "The broad promise did not earn commitment.",
      parents: [{
        ideaId: "idea-parent",
        ideaRevision: 3,
        solutionName: "Signal Desk",
        contribution: "Keep the recurring signal workflow.",
      }],
      evidence: {
        sourceAnchors: [{ ideaId: "idea-parent", ideaRevision: 2, candidateSnapshotSha256: "a".repeat(64), pain: "Missed demand signals" }],
        requiresValidation: ["Validate the narrower buyer."],
        experimentConclusionRefs: [{
          conclusionId: "conclusion-1",
          experimentId: "experiment-1",
          outcome: "FAIL",
          evidenceSource: "MANUAL",
          snapshotSha256: "a".repeat(64),
          evidenceRefs: [],
        }],
      },
      newAssumptions: ["Agencies run weekly renewal reviews."],
    };
    vi.mocked(getSelectionExperiments).mockResolvedValue([experiment] as never);
    vi.mocked(createSelectionIdeaNarrowingProposal).mockResolvedValue({
      proposalMessage: {
        id: "proposal-message-1",
        content: "One narrowed, evaluated variant.",
        patchJson: synthesisPatch,
        createdAt: "2026-07-16T01:00:00.000Z",
      },
      settlement: {
        state: "accepted",
        idea: {
          solution_name: child.solution_name,
          idea_id: "idea-child",
          idea_revision: 1,
          synthesis_operation: "narrow",
          synthesized_from: child.synthesized_from!,
          synthesis_source_message_id: "proposal-message-1",
        },
      },
    } as never);

    page.url = new URL("http://localhost/jobs/job-1?selectionTool=tests") as typeof page.url;
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, solutions: [parent, child], selectedSolutionIds: ["idea-parent"] },
    });
    expect(view.getByText("Workshop variant · Narrowed from Signal Desk")).toBeInTheDocument();
    await waitFor(() => expect(goto).toHaveBeenCalledWith(
      "/jobs/job-1/selection/risks?idea=idea-parent%3A3&tool=tests",
      { replaceState: true },
    ));
    expect(view.queryByRole("dialog", { name: "Test decision assumptions" })).not.toBeInTheDocument();
  });
});

describe("SelectionWorkbench — accepted combined variant", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chatLedger.reset();
    chatPanel.open();
  });

  afterEach(cleanup);

  function combinedFixture(receiptParents?: { idea_id: string; idea_revision: number }[]) {
    const first = solution("Change Monitor", { idea_id: "source-1", idea_revision: 2 });
    const second = solution("Briefing Desk", { idea_id: "source-2", idea_revision: 4 });
    const unrelated = solution("Unrelated Pick", { idea_id: "unrelated", idea_revision: 1 });
    const child = solution("Agency Signal Desk", {
      idea_id: "combined-child",
      idea_revision: 1,
      synthesis_operation: "combine",
      synthesis_source_message_id: "combine-proposal",
      synthesized_from: [
        {
          idea_id: "source-1",
          idea_revision: 2,
          solution_name: "Change Monitor",
          contribution: "Keep the alerting mechanism.",
        },
        {
          idea_id: "source-2",
          idea_revision: 4,
          solution_name: "Briefing Desk",
          contribution: "Keep the client-ready summary.",
        },
      ],
    });
    const proposal = {
      kind: "idea_synthesis" as const,
      operation: "combine" as const,
      proposedTitle: "Agency Signal Desk",
      proposedBrief: "Combines change alerts with a client-ready briefing.",
      changeSummary: "Joins two workflows for the same agency buyer.",
      rationale: "The sources solve adjacent parts of one recurring job.",
      parents: [
        {
          ideaId: "source-1",
          ideaRevision: 2,
          solutionName: "Change Monitor",
          contribution: "Keep the alerting mechanism.",
        },
        {
          ideaId: "source-2",
          ideaRevision: 4,
          solutionName: "Briefing Desk",
          contribution: "Keep the client-ready summary.",
        },
      ],
      evidence: {
        sourceAnchors: [
          { ideaId: "source-1", ideaRevision: 2, candidateSnapshotSha256: "a".repeat(64) },
          { ideaId: "source-2", ideaRevision: 4, candidateSnapshotSha256: "b".repeat(64) },
        ],
        requiresValidation: ["Validate that one buyer owns both workflows."],
      },
      newAssumptions: ["Agencies own both workflows."],
    };
    const receipt = {
      solution_name: "Agency Signal Desk",
      idea_id: "combined-child",
      idea_revision: 1,
      synthesis_operation: "combine" as const,
      synthesized_from: receiptParents ?? [
        { idea_id: "source-1", idea_revision: 2 },
        { idea_id: "source-2", idea_revision: 4 },
      ],
      synthesis_source_message_id: "combine-proposal",
    };
    return {
      solutions: [first, second, unrelated, child],
      messages: [
        {
          id: "combine-proposal",
          gateStage: 5,
          role: "assistant" as const,
          content: "Here is the evaluated combination.",
          patchJson: proposal,
          truncated: false,
          createdAt: "2026-07-16T00:00:00.000Z",
        },
        {
          id: "combine-receipt",
          gateStage: 5,
          role: "receipt" as const,
          content: "",
          patchJson: {
            kind: "ledger_event" as const,
            version: 1,
            event: "seed_settled" as const,
            outcome: "accepted" as const,
            patch: {},
            rows: [],
            sourceMessageId: "combine-proposal",
            idea: receipt,
          },
          truncated: false,
          createdAt: "2026-07-16T00:05:00.000Z",
        },
      ],
    };
  }

  it("routes a three-way exact variant review to the canonical comparison without changing the shortlist", async () => {
    const fixture = combinedFixture();
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: fixture.messages,
      weakPool: false,
    } as never);
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: fixture.solutions,
        selectedSolutionIds: ["source-1", "source-2", "unrelated"],
      },
    });

    const firstChoice = await view.findByLabelText("Deselect Change Monitor") as HTMLInputElement;
    const secondChoice = await view.findByLabelText("Deselect Briefing Desk") as HTMLInputElement;
    const unrelatedChoice = await view.findByLabelText("Deselect Unrelated Pick") as HTMLInputElement;
    const childChoice = await view.findByLabelText("Select Agency Signal Desk") as HTMLInputElement;

    await fireEvent.click(await view.findByRole("button", { name: "Compare with sources" }));
    expect(goto).toHaveBeenCalledWith(
      "/jobs/job-1/selection/compare?idea=source-1%3A2&idea=source-2%3A4&idea=combined-child%3A1&view=market",
    );
    expect(firstChoice.checked).toBe(true);
    expect(secondChoice.checked).toBe(true);
    expect(childChoice.checked).toBe(false);
    expect(unrelatedChoice.checked).toBe(true);
  });

  it("rejects an accepted receipt that omits one exact source revision", async () => {
    const fixture = combinedFixture([{ idea_id: "source-1", idea_revision: 2 }]);
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: fixture.messages,
      weakPool: false,
    } as never);
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: fixture.solutions,
        selectedSolutionIds: ["source-1", "source-2"],
      },
    });

    await fireEvent.click(await view.findByRole("button", { name: "Compare with sources" }));
    expect(await view.findByRole("alert")).toHaveTextContent(
      "The evaluated variant is still syncing. Refresh and try again.",
    );
    expect(view.queryByRole(
      "dialog", { name: "Compare sources and combined variant" },
    )).not.toBeInTheDocument();
    expect((await view.findByLabelText("Deselect Change Monitor") as HTMLInputElement).checked).toBe(true);
    expect((await view.findByLabelText("Deselect Briefing Desk") as HTMLInputElement).checked).toBe(true);
  });

  it("rejects a child stamped by a different synthesis proposal", async () => {
    const fixture = combinedFixture();
    fixture.solutions[3].synthesis_source_message_id = "different-proposal";
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: fixture.messages,
      weakPool: false,
    } as never);
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: fixture.solutions,
        selectedSolutionIds: ["source-1", "source-2"],
      },
    });

    await fireEvent.click(await view.findByRole("button", { name: "Compare with sources" }));
    expect(await view.findByRole("alert")).toHaveTextContent(
      "The evaluated variant is still syncing. Refresh and try again.",
    );
    expect(view.queryByRole(
      "dialog", { name: "Compare sources and combined variant" },
    )).not.toBeInTheDocument();
  });
});

describe("SelectionWorkbench — decision profile synchronization", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chatLedger.reset();
    chatPanel.close();
    vi.mocked(getChatHistory).mockResolvedValue({ messages: [], weakPool: false } as never);
  });

  afterEach(cleanup);

  it("does not let a stale parent refetch clobber a profile saved in the workbench", async () => {
    vi.mocked(saveSelectionDecisionProfile).mockResolvedValue({
      selectionDecisionProfile: SAVED_DECISION_PROFILE,
    });
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, decisionProfile: OLD_DECISION_PROFILE },
    });

    // Phase 1b: the persistent card is a display-only summary row; its own
    // edit button is THE edit entry (label follows the saved profile: a
    // profile is already saved here, so it reads "Edit build limits").
    expect(view.getByLabelText("Build limits summary")).toHaveTextContent("Build limits saved");
    await fireEvent.click(view.getByRole("button", { name: "Edit build limits" }));
    await fireEvent.click(view.getByRole("radio", { name: "Full time" }));
    await fireEvent.click(view.getByRole("button", { name: "Save build limits" }));

    await waitFor(() => expect(saveSelectionDecisionProfile).toHaveBeenCalledWith(
      "job-1",
      SAVED_DECISION_PROFILE,
    ));

    await view.rerender({ ...baseProps, decisionProfile: OLD_DECISION_PROFILE });

    // The saved (newer) profile survives the stale refetch: reopening the
    // editor still shows the saved value, not the stale prop.
    expect(view.getByLabelText("Build limits summary")).toHaveTextContent("Build limits saved");
    await fireEvent.click(view.getByRole("button", { name: "Edit build limits" }));
    expect(view.getByRole("radio", { name: "Full time" })).toHaveAttribute("aria-checked", "true");
  });

  it("keeps a dirty build-limits draft mounted but disables saving during a pool mutation", async () => {
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, decisionProfile: OLD_DECISION_PROFILE },
    });

    await fireEvent.click(view.getByRole("button", { name: "Edit build limits" }));
    await fireEvent.click(view.getByRole("radio", { name: "Full time" }));

    await view.rerender({
      ...baseProps,
      decisionProfile: OLD_DECISION_PROFILE,
      isRegenerating: true,
    });

    expect(view.getByRole("dialog", { name: "Your build limits" })).toBeInTheDocument();
    expect(view.getByRole("radio", { name: "Full time" })).toHaveAttribute("aria-checked", "true");
    expect(view.getByRole("button", { name: "Save build limits" })).toBeDisabled();

    await fireEvent.click(view.getByRole("button", { name: "Save build limits" }));
    expect(saveSelectionDecisionProfile).not.toHaveBeenCalled();

    await view.rerender({
      ...baseProps,
      decisionProfile: OLD_DECISION_PROFILE,
      isRegenerating: false,
    });
    expect(view.getByRole("button", { name: "Save build limits" })).toBeEnabled();
    expect(view.getByRole("radio", { name: "Full time" })).toHaveAttribute("aria-checked", "true");
  });
});

describe("SelectionWorkbench — collaborator feedback", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chatLedger.reset();
    chatPanel.close();
    vi.mocked(getChatHistory).mockResolvedValue({ messages: [], weakPool: false } as never);
  });

  afterEach(cleanup);

  it("groups exact-ID rationales separately and leaves ambiguous legacy feedback unattached", async () => {
    const first = solution("Duplicate", {
      headline: "First workflow",
      idea_id: "idea_first",
      idea_revision: 1,
    });
    const second = solution("Duplicate", {
      headline: "Second workflow",
      idea_id: "idea_second",
      idea_revision: 1,
    });
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: [first, second],
        voteRationales: [
          { solutionId: "idea_first", solutionName: "Duplicate", comment: "Best for finance teams." },
          { solutionId: "idea_second", solutionName: "Duplicate", comment: "Fits a weekly review." },
          { solutionName: "Duplicate", comment: "Legacy note with no stable identity." },
        ],
      },
    });
    await openAppendix(view);

    const disclosure = view.container.querySelector("details.collaborator-feedback");
    expect(disclosure).toBeInTheDocument();
    await fireEvent.click(disclosure!.querySelector("summary")!);

    expect(view.getByRole("button", { name: "First workflow" })).toBeInTheDocument();
    expect(view.getByRole("button", { name: "Second workflow" })).toBeInTheDocument();
    expect(view.getByText("Best for finance teams.")).toBeInTheDocument();
    expect(view.getByText("Fits a weekly review.")).toBeInTheDocument();
    expect(view.getByText("Legacy note with no stable identity.")).toBeInTheDocument();
    expect(view.getByText("Previous or ambiguous idea")).toBeInTheDocument();
  });
});

describe("SelectionWorkbench — contextual analyst guidance", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chatLedger.reset();
    chatPanel.close();
    vi.mocked(getChatHistory).mockResolvedValue({ messages: [], weakPool: false } as never);
    vi.mocked(streamChat).mockResolvedValue(undefined as never);
  });

  afterEach(cleanup);

  it("shows the server-recommended next step while keeping analyst messages owner-initiated", async () => {
    const alpha = solution("Alpha Idea", { idea_id: "idea-alpha", idea_revision: 1 });
    vi.mocked(getSelectionDecisionState).mockResolvedValue({
      schemaVersion: 1,
      jobId: "job-1",
      status: "AWAITING_SELECTION",
      shortlist: { version: 1, items: [{ ideaId: "idea-alpha", ideaRevision: 1 }] },
      profile: null,
      founderFit: null,
      challenges: [],
      ownerEvidence: [],
      assumptions: [],
      experiments: [],
      conclusions: [],
      staleCounts: { shortlist: 0, profile: 0, founderFit: 0, challenges: 0, ownerEvidence: 0, assumptions: 0, experiments: 0, conclusions: 0, total: 0 },
      deepResearch: { eligible: true, optionalWorkRequired: false, blockers: [] },
      nextAction: {
        kind: "capture_assumption",
        target: "assumptions",
        reason: "Capture the unresolved demand risk before paying for deeper research.",
        required: false,
        ideas: [{ ideaId: "idea-alpha", ideaRevision: 1, title: "Alpha Idea" }],
        lens: "DEMAND",
        records: [],
      },
    } as never);

    const view = render(SelectionWorkbench, {
      props: { ...baseProps, solutions: [alpha], selectedSolutionIds: ["idea-alpha"] },
    });

    expect(await view.findByRole("heading", { name: "Save a question to resolve" })).toBeInTheDocument();
    await fireEvent.click(view.getByRole("button", { name: "Ask analyst" }));

    const composer = await view.findByLabelText("Message the analyst") as HTMLTextAreaElement;
    expect(composer.value).toBe("");
    expect(streamChat).not.toHaveBeenCalled();
  });

  // The backend names the records a next action refers to in `records` — the action
  // itself carries no id fields. A test step that drops them deep-links to a planner
  // with no assumption at all. Note what the URL below does NOT carry: `experiment-1`
  // is named in `records` but there is no `experimentId` deep-link param, so this
  // prefills the planner with the assumption — it does not reopen that saved draft.
  it("deep-links the named assumption so Review test draft opens the planner prefilled with it", async () => {
    const alpha = solution("Alpha Idea", { idea_id: "idea-alpha", idea_revision: 1 });
    vi.mocked(getSelectionDecisionState).mockResolvedValue({
      schemaVersion: 1,
      jobId: "job-1",
      status: "AWAITING_SELECTION",
      shortlist: { version: 1, items: [{ ideaId: "idea-alpha", ideaRevision: 1 }] },
      profile: null,
      founderFit: null,
      challenges: [],
      ownerEvidence: [],
      assumptions: [],
      experiments: [],
      conclusions: [],
      staleCounts: { shortlist: 0, profile: 0, founderFit: 0, challenges: 0, ownerEvidence: 0, assumptions: 0, experiments: 0, conclusions: 0, total: 0 },
      deepResearch: { eligible: true, optionalWorkRequired: false, blockers: [] },
      nextAction: {
        kind: "review_test_brief",
        target: "experiments",
        reason: "Review and lock the draft before collecting evidence.",
        required: false,
        ideas: [{ ideaId: "idea-alpha", ideaRevision: 1, title: "Alpha Idea" }],
        lens: "demand",
        records: [
          { kind: "assumption", id: "assumption-1", version: 2 },
          { kind: "experiment", id: "experiment-1" },
        ],
      },
    } as never);

    const view = render(SelectionWorkbench, {
      props: { ...baseProps, solutions: [alpha], selectedSolutionIds: ["idea-alpha"] },
    });

    await fireEvent.click(await view.findByRole("button", { name: "Review test draft" }));

    await waitFor(() => expect(goto).toHaveBeenCalledWith(
      "/jobs/job-1/selection/risks?idea=idea-alpha%3A1&tool=tests&ideaId=idea-alpha&ideaRevision=1&assumptionId=assumption-1",
    ));
  });
});

describe("SelectionWorkbench — below-table IA (Phase 1b)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chatLedger.reset();
    chatPanel.close();
    vi.mocked(getChatHistory).mockResolvedValue({ messages: [], weakPool: false } as never);
  });

  afterEach(cleanup);

  const RULED_OUT_ONE: RuledOutFinding[] = [{
    pain_title: "Manual reconciliation",
    reason: "No buyer identified",
    market_fit: 0.15,
    market_fit_band: "very-low",
    prior_tier: "backfill",
    source: "backfill_rejected",
    evidence: "",
  }];

  it("folds the stats into the header as one record line (no boxed stat cells)", () => {
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, segmentCount: 4 },
    });

    const stats = view.getByLabelText("Idea summary");
    expect(stats).toHaveClass("record-line");
    expect(stats.textContent).toMatch(/^2 ideas · Top score \d+ · 4 segments$/);
    expect(view.container.querySelector(".cmd-proof")).toBeNull();
  });

  it("omits null metrics from the header record line instead of rendering placeholders", () => {
    const view = render(SelectionWorkbench, { props: baseProps });

    const stats = view.getByLabelText("Idea summary");
    expect(stats.textContent).toMatch(/^2 ideas · Top score \d+$/);
    expect(stats).not.toHaveTextContent("--");
  });

  it("renders settled batch history after the ranked list in validate mode", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [{
        id: "batch-receipt-settled",
        gateStage: 5,
        role: "receipt",
        content: "Batch settled",
        patchJson: {
          kind: "ledger_event",
          version: 1,
          event: "regeneration_settled",
          patch: {},
          rows: [],
          operationId: "generation-op-settled",
          batch: {
            ordinal: 1,
            focus: "novelty",
            outcome: "completed",
            generatedCount: 2,
            addedCount: 2,
            addedIdeaIds: ["idea-alpha", "idea-beta"],
          },
        },
        createdAt: "2026-08-09T00:00:00.000Z",
      }],
      weakPool: false,
    } as never);
    await chatLedger.init("job-1");

    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        groupByThesis: false,
        headerTitle: "Your idea, ranked with the alternatives",
      },
    });

    const heading = view.getByRole("heading", {
      name: "Your idea, ranked with the alternatives",
    });
    const rankedList = view.getByRole("table", { name: "Ranked ideas" });
    const history = view.getByText("Additional batches").closest("section");
    if (!history) throw new Error("Expected settled batch history section");

    expect(heading.compareDocumentPosition(rankedList) & Node.DOCUMENT_POSITION_FOLLOWING)
      .not.toBe(0);
    expect(rankedList.compareDocumentPosition(history) & Node.DOCUMENT_POSITION_FOLLOWING)
      .not.toBe(0);
    expect(view.queryByLabelText("Idea batch in progress")).toBeNull();
    expect(view.getByText("1 batch run")).toBeInTheDocument();
    expect(view.getByText("Batch 1 · Differentiation focus")).toBeInTheDocument();
    expect(view.getByRole("button", { name: "Review new candidates" })).toBeInTheDocument();
  });

  it("separates append-batch generation from branching a specific direction", async () => {
    const view = render(SelectionWorkbench, { props: baseProps });

    expect(view.queryByText("Need another angle?")).toBeNull();
    expect(await view.findByRole("button", { name: "Add another batch" })).toBeInTheDocument();
    expect(await view.findByRole("button", { name: /Branch a new direction/ })).toBeInTheDocument();
    expect(view.getByText(/Existing candidate scores and your shortlist stay unchanged; the ranked list may reorder/)).toBeInTheDocument();

    await fireEvent.click(view.getByRole("button", { name: "Add another batch" }));
    expect(view.getByRole("dialog", { name: "Add another batch" })).toBeInTheDocument();
    expect(view.getByText(/Existing candidate scores and your shortlist stay unchanged; the list may reorder/)).toBeInTheDocument();
  });

  it("submits an idempotent, price-confirmed differentiation batch", async () => {
    const view = render(SelectionWorkbench, { props: baseProps });

    await fireEvent.click(await view.findByRole("button", { name: "Add another batch" }));
    await fireEvent.click(view.getByRole("button", { name: "Differentiation" }));
    await fireEvent.click(view.getByRole("button", { name: "Add another batch · 2 credits" }));

    await waitFor(() => expect(regenerateIdeas).toHaveBeenCalledWith(
      "job-1",
      {
        clientRequestId: expect.any(String),
        expectedCost: 2,
        idea_focus: "novelty",
      },
    ));
  });

  it("keeps completed batch usage and the disabled add control visible at the cap", () => {
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        canRegenerate: false,
        decisionTools: false,
        ideaBatchCompletedCount: 10,
        maxIdeaBatches: 10,
      },
    });

    expect(view.getByText("10 of 10 additional batches used")).toBeInTheDocument();
    expect(view.getByRole("button", { name: "Add another batch" })).toBeDisabled();
    expect(view.getByText("Idea batch limit reached")).toBeInTheDocument();
  });

  it("opens the add-batch dialog from a recoverable history deep link", async () => {
    page.url = new URL(`http://localhost/jobs/job-1?addBatch=1#${RANKED_IDEAS_ANCHOR}`) as typeof page.url;
    const view = render(SelectionWorkbench, { props: baseProps });

    expect(await view.findByRole("dialog", { name: "Add another batch" })).toBeInTheDocument();
    expect(replaceState).toHaveBeenCalledWith(
      `/jobs/job-1#${RANKED_IDEAS_ANCHOR}`,
      page.state,
    );
  });

  it("turns a timed-out batch poll into a manual status check", async () => {
    vi.useFakeTimers();
    try {
      const pendingHistory = {
        messages: [{
          id: "batch-receipt-pending",
          gateStage: 5,
          role: "receipt",
          content: "Adding another batch",
          patchJson: {
            kind: "ledger_event",
            version: 1,
            event: "regeneration_submitted",
            patch: {},
            rows: [],
            operationId: "generation-op-pending",
            batch: {
              ordinal: 4,
              focus: "auto",
            },
          },
          createdAt: "2026-07-27T00:00:00.000Z",
        }],
        weakPool: false,
      };
      vi.mocked(getChatHistory).mockResolvedValue(pendingHistory as never);
      await chatLedger.init("job-1");
      const view = render(SelectionWorkbench, { props: baseProps });

      expect(view.getByText("Adding another batch")).toBeInTheDocument();
      const liveNotice = view.getByLabelText("Idea batch in progress");
      const rankedList = view.getByRole("table", { name: "Ranked ideas" });
      expect(liveNotice.compareDocumentPosition(rankedList) & Node.DOCUMENT_POSITION_FOLLOWING)
        .not.toBe(0);
      expect(view.queryByText("Additional batches")).toBeNull();
      await vi.advanceTimersByTimeAsync(200 * 6000);

      expect(view.getByText(/Automatic checks paused/)).toBeInTheDocument();
      await fireEvent.click(view.getByRole("button", { name: "Check status" }));
      expect(view.queryByText(/Automatic checks paused/)).not.toBeInTheDocument();
      expect(getChatHistory).toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  }, 20000);

  it("opens the ruled-out record stamped with the durable generation operation id", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [{
        id: "batch-receipt-1",
        gateStage: 5,
        role: "receipt",
        content: "No candidates added",
        patchJson: {
          kind: "ledger_event",
          version: 1,
          event: "regeneration_settled",
          patch: {},
          rows: [],
          operationId: "generation-op-1",
          batch: {
            ordinal: 2,
            outcome: "no_candidates_added",
            addedCount: 0,
            ruledOutCount: 1,
          },
        },
        createdAt: "2026-07-27T00:00:00.000Z",
      }],
    } as never);
    await chatLedger.init("job-1");
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        examinedRuledOut: [{
          ...RULED_OUT_ONE[0],
          generation_operation_id: "generation-op-1",
        }],
      },
    });

    await fireEvent.click(await view.findByRole("button", { name: "Review ruled-out ideas" }));

    expect(view.getByRole("button", { name: /Discovery appendix/i })).toHaveAttribute("aria-expanded", "true");
    expect(view.getByText("Manual reconciliation")).toBeInTheDocument();
  });

  it("marks job-page direction launches so closing returns to the exact originating page", async () => {
    page.url = new URL("http://localhost/jobs/job-1?source=shortlist#ideas") as typeof page.url;
    page.state = { openId: "context-note" } as typeof page.state;
    const identified = [
      solution("Alpha Idea", { idea_id: "idea-alpha", idea_revision: 2 }),
      solution("Beta Idea", { idea_id: "idea-beta", idea_revision: 4 }),
    ];
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: identified,
        selectedSolutionIds: ["idea-alpha", "idea-beta"],
      },
    });

    await fireEvent.click(await view.findByRole("button", { name: /Branch a new direction/ }));

    expect(goto).toHaveBeenCalledWith(
      "/jobs/job-1/selection/compare?idea=idea-alpha%3A2&idea=idea-beta%3A4&tool=variants",
      {
        state: {
          openId: "context-note",
          selectionToolOrigin: {
            tool: "variants",
            jobId: "job-1",
            returnHref: "/jobs/job-1?source=shortlist#ideas",
            historyOwned: true,
          },
        },
      },
    );
  });

  // Data caveats change how the scores and counts above them read, so they sit at
  // the FIRST level. They used to be filed inside the collapsed appendix, which put
  // them behind two disclosures — and `appendixMeta` never counted them, so nothing
  // on the collapsed appendix hinted they were there.
  it("keeps the opportunity-shape line and the data caveats both at the first level", async () => {
    const angled = [
      solution("Alpha Idea", { winning_angle: "vertical_workflow" }),
      solution("Beta Idea", { winning_angle: "vertical_workflow" }),
      solution("Gamma Idea", { winning_angle: "vertical_workflow" }),
    ];
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, solutions: angled, coverageNotes: ["Sampling skews to Reddit."] },
    });

    expect(view.getByText(
      "Workflow-leaning niche: 3 of 3 viable ideas win by owning a deep workflow for a specific user.",
    )).toBeInTheDocument();

    const caveats = view.getByText("Data caveats");
    expect(caveats).toBeVisible();
    // Its own <details> is the ONLY disclosure between it and the page.
    expect(caveats.closest(".appendix-body")).toBeNull();
  });

  it("renders no appendix at all when the data caveats are the only secondary content", () => {
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, coverageNotes: ["Sampling skews to Reddit."] },
    });

    expect(view.getByText("Data caveats")).toBeVisible();
    expect(view.queryByRole("button", { name: /Discovery appendix/i })).toBeNull();
  });

  it("shows the appendix meta counts for collaborator and ruled-out records", async () => {
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: [solution("Alpha Idea", { idea_id: "idea-alpha" })],
        examinedRuledOut: RULED_OUT_ONE,
        voteRationales: [
          { solutionId: "idea-alpha", solutionName: "Alpha Idea", comment: "Best fit." },
          { solutionId: "idea-alpha", solutionName: "Alpha Idea", comment: "Clear buyer." },
        ],
      },
    });

    const trigger = await view.findByRole("button", { name: /Discovery appendix/i });
    expect(trigger).toHaveTextContent("2 feedback notes · 1 idea ruled out");
    expect(trigger).not.toHaveTextContent("analyst note");
  });

  it("renders no appendix when there is nothing to file", () => {
    const view = render(SelectionWorkbench, { props: baseProps });

    expect(view.queryByRole("button", { name: /Discovery appendix/i })).toBeNull();
  });

  it("shows the display-only founder-context row with exactly one edit entry once a profile is saved", async () => {
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, decisionProfile: OLD_DECISION_PROFILE },
    });

    await view.findByRole("complementary", { name: "Ideas for Deep Research" });
    const row = view.getByLabelText("Build limits summary");
    expect(row).toHaveTextContent("Build limits saved");
    expect(row).toHaveTextContent("Under 10 hrs / week");
    expect(row).toHaveTextContent("Under $1k");
    expect(row).toHaveTextContent("Solo");
    expect(row).toHaveTextContent("Revenue within 90 days");
    expect(row).toHaveTextContent("SEO");
    // The row owns exactly one edit button; nothing else on the page duplicates it
    // (DecisionGuide no longer renders a founder-context entry of its own).
    expect(row.querySelectorAll("button")).toHaveLength(1);
    expect(view.getAllByRole("button", { name: "Edit build limits" })).toHaveLength(1);
    expect(view.queryByText("Your build limits")).not.toBeInTheDocument();
  });

  it("visitor view also withholds unbound recommendation prose", async () => {
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        interactive: false,
        examinedRuledOut: RULED_OUT_ONE,
        ideaPortfolioSummary: [
          "The pool has moderate market fit overall.",
          "Alpha Idea most deserves deeper validation because it has the clearest buyer.",
        ].join("\n\n"),
      },
    });

    // No appendix or founder row on the shared surface.
    expect(view.queryByRole("button", { name: /Discovery appendix/i })).toBeNull();
    expect(view.queryByLabelText("Build limits summary")).toBeNull();
    expect(await view.findByLabelText("Discovery take")).toHaveTextContent(
      "stored recommendation is not bound to exact current idea revisions",
    );
    expect(view.queryByLabelText("Research recommendation")).toBeNull();
    expect(
      view.getByRole("heading", { name: "Ideas that did not clear the market-fit check" }),
    ).toBeInTheDocument();
  });
});

describe("SelectionWorkbench — dead-end escapes (Phase 2)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chatLedger.reset();
    chatPanel.open();
    vi.mocked(getChatHistory).mockResolvedValue({ messages: [], weakPool: false } as never);
    // Earlier describes queue non-empty mockResolvedValue payloads that
    // clearAllMocks does not remove; restore the empty-workspace defaults.
    vi.mocked(getSelectionExperiments).mockResolvedValue([] as never);
    vi.mocked(getSelectionChallenges).mockResolvedValue({ challenges: [], stale: [] } as never);
  });

  afterEach(() => {
    cleanup();
  });

  const alphaSolutions = [solution("Alpha Idea", { idea_id: "idea-alpha", idea_revision: 1 })];

  function alphaDemandChallenge() {
    return {
      id: "challenge-alpha",
      version: 1,
      inputFingerprint: "f".repeat(64),
      ideaId: "idea-alpha",
      ideaRevision: 1,
      ideaTitle: "Alpha Idea",
      lens: "demand" as const,
      overall: "weakened" as const,
      ideaSnapshot: { solution_name: "Alpha Idea" },
      subjectSnapshot: [],
      evidenceSnapshot: [],
      questions: [{
        questionId: "pain_is_observed",
        consensus: "insufficient" as const,
        skeptic: {
          questionId: "pain_is_observed",
          position: "insufficient" as const,
          summary: "No recurring pain is captured.",
          subjectKeys: [],
          evidenceKeys: [],
          evidenceClass: "inference" as const,
        },
        auditor: {
          questionId: "pain_is_observed",
          position: "insufficient" as const,
          summary: "The record cannot answer this question.",
          subjectKeys: [],
          evidenceKeys: [],
          evidenceClass: "inference" as const,
        },
      }],
      skepticModel: "model-skeptic",
      auditorModel: "model-auditor",
      promptVersion: 1,
      createdAt: "2026-07-16T00:00:00.000Z",
    };
  }

  it("routes a legacy test link to the evidence workspace with the planner open", async () => {
    page.url = new URL("http://localhost/jobs/job-1?selectionTool=tests") as typeof page.url;
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, solutions: alphaSolutions, selectedSolutionIds: ["idea-alpha"] },
    });

    await waitFor(() => expect(goto).toHaveBeenCalledWith(
      "/jobs/job-1/selection/risks?idea=idea-alpha%3A1&tool=tests",
      { replaceState: true },
    ));
    expect(view.queryByRole("dialog", { name: "Test decision assumptions" })).not.toBeInTheDocument();
  });

  it("routes a legacy risk link to the canonical evidence workspace", async () => {
    vi.mocked(getSelectionChallenges).mockResolvedValue({
      challenges: [alphaDemandChallenge()],
      stale: [],
    } as never);
    page.url = new URL("http://localhost/jobs/job-1?selectionTool=risks") as typeof page.url;
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, solutions: alphaSolutions, selectedSolutionIds: ["idea-alpha"] },
    });

    await waitFor(() => expect(goto).toHaveBeenCalledWith(
      "/jobs/job-1/selection/risks?idea=idea-alpha%3A1&tool=challenge",
      { replaceState: true },
    ));
    expect(view.queryByRole("dialog", { name: "Check risks for shortlisted ideas" })).not.toBeInTheDocument();
  });
});

/* ── Ranked-candidates ARIA table semantics ──
 * The ranked list is a CSS-grid "visual table" built from divs/spans. It carries
 * explicit ARIA table roles so each value is announced with its column name,
 * which is what lets us drop the per-cell aria-labels that used to compensate. */
describe("SelectionWorkbench — ranked candidates table semantics", () => {
  it("exposes the ranked list as a table with the expected column headers", () => {
    const view = render(SelectionWorkbench, { props: baseProps });
    const table = view.getByRole("table", { name: "Ranked ideas" });

    expect(within(table).getAllByRole("columnheader")).toHaveLength(7);

    for (const label of ["#", "Select", "Idea", "Score /100", "Market fit", "Feasibility", "Build time"]) {
      expect(
        within(table).getByRole("columnheader", { name: label }),
      ).toBeInTheDocument();
    }
  });

  it("gives each candidate a row whose cells line up with the columns", () => {
    const view = render(SelectionWorkbench, { props: baseProps });
    const table = view.getByRole("table", { name: "Ranked ideas" });

    // header row + one row per solution
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(SOLUTIONS.length + 1);

    const alphaRow = rows.find((r) => r.textContent?.includes("Alpha Idea")) as HTMLElement;
    expect(alphaRow).toBeTruthy();

    // The candidate identity is a rowheader so the row announces itself first.
    const rowHeader = within(alphaRow).getByRole("rowheader");
    expect(rowHeader).toHaveTextContent("Alpha Idea");

    // rank + pick + 4 metric cells; the title is the rowheader, not a cell.
    const cells = within(alphaRow).getAllByRole("cell");
    expect(cells).toHaveLength(6);

    // Column order is positional: rank, pick, score, market fit, feasibility, build.
    expect(cells[0]).toHaveTextContent("1");
    expect(cells[3]).toHaveTextContent("60"); // market_fit_score 0.6
    expect(cells[4]).toHaveTextContent("60"); // technical_feasibility_score 0.6
    expect(cells[5]).toHaveTextContent("2 weeks");
  });

  it("labels red-team evidence as an adversarial finding rather than a fake incumbent", () => {
    const candidate = solution("Evidence-challenged idea", {
      incumbent_parity: "shipped by evidence: the proposed data route misses the buyer",
      red_team_verdict: "killed",
      red_team_caveats: ["The modal buyer has no SEC filing."],
    });
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, solutions: [candidate] },
    });
    const row = within(view.getByRole("table", { name: "Ranked ideas" }))
      .getAllByRole("row")
      .find((entry) => entry.textContent?.includes("Evidence-challenged idea")) as HTMLElement;

    expect(row).toHaveTextContent("Premise unproven");
    expect(row).not.toHaveTextContent("Incumbent: Evidence");
  });

  it("says what a premise-unproven chip means, and cites the objection behind it", () => {
    const candidate = solution("FaxCorrectionCache", {
      adjusted_composite_score: 0.71,
      red_team_verdict: "killed",
      red_team_caveats: ["No reachable buyer owns the fax queue."],
    });
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, solutions: [candidate] },
    });
    const row = within(view.getByRole("table", { name: "Ranked ideas" }))
      .getAllByRole("row")
      .find((entry) => entry.textContent?.includes("FaxCorrectionCache")) as HTMLElement;

    // The chip names the state; the description carries the meaning, the cited caveat,
    // and why the score next to it is still high.
    expect(row).toHaveTextContent("Premise unproven");
    expect(row).not.toHaveTextContent("Killed");
    expect(row).toHaveTextContent(/could not find evidence for this idea's premise/);
    expect(row).toHaveTextContent("No reachable buyer owns the fax queue.");
    expect(row).toHaveTextContent(/other scores describe how well it would work if the premise holds/);
  });

  it("does not invent a score-versus-recommendation split from prose", () => {
    const ideas = [
      solution("FaxCorrectionCache", {
        idea_id: "idea-fax",
        idea_revision: 1,
        adjusted_composite_score: 0.71,
        red_team_verdict: "killed",
        red_team_caveats: ["No reachable buyer owns the fax queue."],
      }),
      solution("CountPad Vet", {
        idea_id: "idea-countpad",
        idea_revision: 1,
        adjusted_composite_score: 0.6,
      }),
    ];
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: ideas,
        ideaPortfolioSummaryFingerprint: portfolioFingerprint(ideas),
        ideaPortfolioSummary: "CountPad Vet is the strongest candidate to validate first.",
      },
    });

    expect(view.queryByRole("note", {
      name: "Why the top-scoring idea is not the recommendation",
    })).toBeNull();
    expect(view.container.querySelectorAll('[data-tour="recommendation-split"]')).toHaveLength(0);
    expect(view.queryByText("Recommended")).toBeNull();

    // The withheld recommendation costs the leader nothing else: it keeps its row and
    // its select control.
    const row = within(view.getByRole("table", { name: "Ranked ideas" }))
      .getAllByRole("row")
      .find((entry) => entry.textContent?.includes("FaxCorrectionCache")) as HTMLElement;
    expect(within(row).getByRole("checkbox", { name: "Select FaxCorrectionCache" })).toBeEnabled();
  });

  it("does not badge a top-scoring idea from matching recommendation prose", () => {
    const ideas = [
      solution("CountPad Vet", {
        idea_id: "idea-countpad",
        idea_revision: 1,
        adjusted_composite_score: 0.71,
      }),
      solution("FaxCorrectionCache", {
        idea_id: "idea-fax",
        idea_revision: 1,
        adjusted_composite_score: 0.6,
      }),
    ];
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: ideas,
        ideaPortfolioSummaryFingerprint: portfolioFingerprint(ideas),
        ideaPortfolioSummary: "CountPad Vet is the strongest candidate to validate first.",
      },
    });

    expect(view.queryByRole("note", {
      name: "Why the top-scoring idea is not the recommendation",
    })).toBeNull();
    expect(view.queryByText(/Premise unproven/)).toBeNull();
    expect(view.queryByText("Recommended")).toBeNull();
  });

  it("chips an idea that serves an adjacent audience, and only when it was judged so", () => {
    const rowFor = (candidate: ReturnType<typeof solution>, title: string) => {
      const view = render(SelectionWorkbench, {
        props: { ...baseProps, solutions: [candidate] },
      });
      const row = within(view.getByRole("table", { name: "Ranked ideas" }))
        .getAllByRole("row")
        .find((entry) => entry.textContent?.includes(title)) as HTMLElement;
      return { row, view };
    };

    const adjacent = rowFor(
      solution("Adjacent idea", { audience_fit: false }),
      "Adjacent idea",
    );
    expect(adjacent.row).toHaveTextContent("Adjacent audience");
    adjacent.view.unmount();

    // True and "not judged" (null / absent) must NOT chip — only an explicit false is a watch-out.
    for (const [fit, title] of [
      [true, "Primary idea"],
      [null, "Untagged idea"],
      [undefined, "Absent idea"],
    ] as const) {
      const view = rowFor(solution(title, { audience_fit: fit }), title);
      expect(view.row).not.toHaveTextContent("Adjacent audience");
      view.view.unmount();
    }
  });

  it("does not re-state column names as aria-labels on non-interactive cells", () => {
    const view = render(SelectionWorkbench, { props: baseProps });
    const table = view.getByRole("table", { name: "Ranked ideas" });

    for (const cell of within(table).getAllByRole("cell")) {
      expect(cell).not.toHaveAttribute("aria-label");
    }
  });

  it("offers no column sorting on either the grouped or the flat board", () => {
    // Sorting was a leaderboard control on a screen that is now a portfolio of buyer-job
    // cards. It could only reorder cards (breaking the "a card you have read stays put"
    // promise) or renumber rows inside them, which is what made the rank column look
    // broken. The columns are labels; the Discovery ranking is the only order.
    const view = render(SelectionWorkbench, { props: baseProps });
    const table = view.getByRole("table", { name: "Ranked ideas" });

    for (const label of ["Score /100", "Market fit", "Feasibility", "Build time"]) {
      const header = within(table).getByRole("columnheader", { name: label });
      expect(header).not.toHaveAttribute("aria-sort");
      expect(within(header).queryByRole("button", { name: label })).toBeNull();
    }
    expect(view.queryByRole("button", { name: /^Sort by / })).toBeNull();
  });

  it("exposes metric definitions through native, keyboard-focusable help buttons", async () => {
    const view = render(SelectionWorkbench, { props: baseProps });
    const table = view.getByRole("table", { name: "Ranked ideas" });
    const scoreHeader = within(table).getByRole("columnheader", { name: "Score /100" });
    const help = scoreHeader.querySelector<HTMLButtonElement>(".metric-help");

    expect(help).not.toBeNull();
    expect(help).toHaveAttribute("type", "button");
    expect(help).toHaveAccessibleName("More information");

    const descriptionId = help!.getAttribute("aria-describedby");
    expect(document.getElementById(descriptionId!)).toHaveTextContent(
      SCORE_DEFINITIONS.composite,
    );

    await fireEvent.focus(help!);
    await waitFor(() => expect(
      document.querySelector(".tooltip-portal-content"),
    ).toHaveTextContent(SCORE_DEFINITIONS.composite));
  });

  it("does not nest interactive tooltip controls inside the row details button", () => {
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: [solution("Alpha Idea", {
          winning_angle: "vertical_workflow",
          angle_rationale: "Own the full workflow for one buyer.",
        })],
      },
    });
    const details = view.getByRole("button", { name: /^Review details for Alpha Idea/ });
    const inlineTooltip = details.querySelector<HTMLElement>(".tooltip-wrapper");

    expect(details.querySelector("button")).toBeNull();
    expect(inlineTooltip).not.toHaveAttribute("role");
    expect(inlineTooltip).not.toHaveAttribute("tabindex");
  });

  it("keeps the pick control and the row details button reachable by name", async () => {
    const view = render(SelectionWorkbench, { props: baseProps });
    const table = view.getByRole("table", { name: "Ranked ideas" });

    const details = within(table).getByRole("button", { name: /^Review details for Alpha Idea/ });
    expect(details).toBeInTheDocument();

    const pick = within(table).getByRole("checkbox", { name: "Select Alpha Idea" });
    expect(pick).toBeInTheDocument();

    await fireEvent.click(pick);
    await waitFor(() =>
      expect(
        within(table).getByRole("checkbox", { name: "Deselect Alpha Idea" }),
      ).toBeInTheDocument(),
    );
  });
});

describe("SelectionWorkbench without the decision tools grant", () => {
  it("hides optional decision tools but keeps append-batch generation available", async () => {
    const granted = render(SelectionWorkbench, { props: baseProps });
    await waitFor(() =>
      expect(granted.getByText("Optional next check")).toBeInTheDocument(),
    );
    expect(granted.getByText("Have a specific direction in mind?")).toBeInTheDocument();
    cleanup();

    const view = render(SelectionWorkbench, {
      props: { ...baseProps, decisionTools: false },
    });
    await waitFor(() =>
      expect(view.getAllByText("Alpha Idea").length).toBeGreaterThan(0),
    );

    expect(view.queryByText("Optional next check")).toBeNull();
    expect(view.queryByLabelText("Optional checks progress")).toBeNull();
    expect(view.queryByText("Have a specific direction in mind?")).toBeNull();
    expect(view.getByRole("button", { name: "Add another batch" })).toBeInTheDocument();
  });

  it("fails closed when the prop is omitted", async () => {
    const { decisionTools: _omitted, ...withoutProp } = baseProps;
    const view = render(SelectionWorkbench, { props: withoutProp });
    await waitFor(() =>
      expect(view.getAllByText("Alpha Idea").length).toBeGreaterThan(0),
    );
    expect(view.queryByText("Optional next check")).toBeNull();
  });
});

describe("SelectionWorkbench — thesis partition", () => {
  const THESIS_SOLUTIONS = [
    solution("Alpha Idea", { idea_id: "idea-alpha", headline: "Order desk lead" }),
    solution("Beta Idea", { idea_id: "idea-beta", headline: "Order desk variant" }),
    solution("Gamma Idea", { idea_id: "idea-gamma", headline: "Billing capture" }),
  ];

  const members = (...names: string[]): ThesisMember[] => names.map((name) => ({ name }));

  const THESES: IdeaThesis[] = [
    {
      family_id: "fam-order",
      display_label: "Controlled-order desk",
      buyer: "Practice manager",
      triggering_job: "File a Form 222 order",
      economic_outcome: "Avoids a compliance write-up",
      members: members("Alpha Idea", "Beta Idea"),
      lead_idea_name: "Alpha Idea",
      incumbent_status: "occupied",
      incumbent_vendors: ["McKesson CSOS"],
      fatal_assumptions: [{
        idea_name: "Alpha Idea",
        source_field: "incumbent_parity",
        assumption: "Buyers will leave their wholesaler portal",
      }],
    },
    {
      family_id: "fam-billing",
      display_label: "Consumption-to-billing capture",
      buyer: "Practice owner",
      triggering_job: "Bill medication actually used",
      economic_outcome: "Recovers leaked revenue",
      members: members("Gamma Idea"),
      lead_idea_name: "Gamma Idea",
      incumbent_status: "open",
      incumbent_vendors: [],
      fatal_assumptions: [],
    },
  ];

  const UNCOVERED: UncoveredFamily[] = [
    {
      family_id: "fam-csos",
      display_label: "Teams manage DEA Form 222 and CSOS orders manually",
      member_pain_ids: ["pain-3", "pain-7"],
      reason: "no_cell_allocated",
      reason_detail: "no generator cell was ever allocated to this family",
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    chatLedger.reset();
    chatPanel.close();
    vi.mocked(getChatHistory).mockResolvedValue({ messages: [], weakPool: false } as never);
  });

  afterEach(cleanup);

  it("nests variants under one card per thesis, collapsed to the lead idea", async () => {
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, solutions: THESIS_SOLUTIONS, ideaTheses: THESES },
    });

    await waitFor(() => expect(view.getByText("Controlled-order desk")).toBeInTheDocument());
    expect(view.getByText("Consumption-to-billing capture")).toBeInTheDocument();
    // Thesis-level context: buyer/job/outcome, incumbent status, fatal assumption.
    expect(view.getByText("Practice manager · File a Form 222 order · Avoids a compliance write-up"))
      .toBeInTheDocument();
    expect(view.getByText("Incumbent: occupied")).toBeInTheDocument();
    expect(view.getByText("Incumbent: no direct tool found")).toBeInTheDocument();
    // Flags are a COUNT, not a sentence in a chip; the text lives in the disclosure the
    // count opens, attributed to the one variant that carries it.
    const flagToggle = view.getByRole("button", { name: "1 flagged assumption" });
    expect(view.getByText("Buyers will leave their wholesaler portal")).not.toBeVisible();
    await fireEvent.click(flagToggle);
    expect(view.getByText("Buyers will leave their wholesaler portal")).toBeVisible();
    expect(view.getByText("Fatal assumption")).toBeVisible();
    // Attributed to the ONE variant that carries it, not asserted of the thesis.
    expect(view.getByText("Alpha Idea")).toBeVisible();

    // Lead visible, variant collapsed.
    expect(view.getByLabelText("Select Order desk lead")).toBeInTheDocument();
    expect(view.getByLabelText("Select Billing capture")).toBeInTheDocument();
    expect(view.queryByLabelText("Select Order desk variant")).toBeNull();

    // ...and still reachable, so nothing selectable before is unselectable now.
    await fireEvent.click(view.getByRole("button", { name: "Show 1 variant" }));
    const variant = view.getByLabelText("Select Order desk variant") as HTMLInputElement;
    await fireEvent.click(variant);
    expect((view.getByLabelText("Deselect Order desk variant") as HTMLInputElement).checked)
      .toBe(true);
  });

  it("keeps a shortlisted variant visible even while its thesis is collapsed", async () => {
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: THESIS_SOLUTIONS,
        ideaTheses: THESES,
        selectedSolutionIds: ["idea-beta"],
      },
    });

    await waitFor(() => expect(
      (view.getByLabelText("Deselect Order desk variant") as HTMLInputElement).checked,
    ).toBe(true));
  });

  it("anchors returns and the tutorial to the first visible grouped row", async () => {
    // REGRESSION: the anchor used to ride the row with global rank 0. Beta outscores
    // everything AND is a variant of the first thesis, so it renders only when that card
    // is expanded — the tutorial step had nothing to point at and driver.js pinned it to
    // the bottom of the screen with no arrow.
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: [
          solution("Alpha Idea", {
            idea_id: "idea-alpha",
            headline: "Order desk lead",
            adjusted_composite_score: 0.5,
          }),
          solution("Beta Idea", {
            idea_id: "idea-beta",
            headline: "Order desk variant",
            adjusted_composite_score: 0.9,
          }),
          solution("Gamma Idea", {
            idea_id: "idea-gamma",
            headline: "Billing capture",
            adjusted_composite_score: 0.6,
          }),
        ],
        ideaTheses: THESES,
      },
    });

    await waitFor(() => expect(view.getByText("Controlled-order desk")).toBeInTheDocument());
    expect(view.queryByLabelText("Select Order desk variant")).toBeNull();

    const anchors = view.container.querySelectorAll('[data-tour="shortlist-checkbox"]');
    expect(anchors).toHaveLength(1);
    expect(anchors[0].querySelector("input")).toHaveAttribute(
      "aria-label",
      "Select Order desk lead",
    );
    const returnAnchor = view.container.querySelector(`#${RANKED_IDEAS_ANCHOR}`);
    expect(returnAnchor).toHaveClass("opp-row");
    expect(returnAnchor).toHaveTextContent("Order desk lead");
    expect(returnAnchor?.querySelector("input")).toHaveAttribute(
      "aria-label",
      "Select Order desk lead",
    );
    expect(view.queryByLabelText("Select Order desk variant")).toBeNull();

    // One card head and one column head, so neither of those steps can pick a row at
    // random either.
    expect(view.container.querySelectorAll('[data-tour="thesis-group"]')).toHaveLength(1);
    expect(view.container.querySelectorAll('[data-tour="ranked-list"]')).toHaveLength(1);
  });

  it("anchors returns and the tutorial to the first visible flat row", async () => {
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, solutions: THESIS_SOLUTIONS },
    });

    await waitFor(() => expect(view.getByText("Order desk lead")).toBeInTheDocument());
    expect(view.container.querySelectorAll('[data-tour="shortlist-checkbox"]')).toHaveLength(1);
    expect(view.container.querySelectorAll('[data-tour="thesis-group"]')).toHaveLength(0);
    const returnAnchor = view.container.querySelector(`#${RANKED_IDEAS_ANCHOR}`);
    expect(returnAnchor).toHaveClass("opp-row");
    expect(returnAnchor).toHaveTextContent("Billing capture");
    expect(returnAnchor?.querySelector("input")).toHaveAttribute(
      "aria-label",
      "Select Billing capture",
    );
  });

  // The fixture is the CAPTURED verdict from
  // output/checkpoints/preview_report_51a491dc-c095-4e21-befb-5cadf540629a.json — never
  // retyped. An earlier version of this test rewrote every em dash to a colon so the
  // sanitizer's regex would match, which is exactly how a rule keyed on `yet:` shipped
  // green against a pipeline that emits `yet —`. If a rule and the fixture disagree, the
  // RULE is wrong. See buyerFacingResearchProse.test.ts for the byte-equality guard.
  it("rewrites pipeline-facing prose from the real exemplar before rendering it", async () => {
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        ideaPortfolioSummary: nicheVerdictExemplar.idea_portfolio_summary,
        nicheDifficultyVerdict: nicheVerdictExemplar.niche_difficulty_verdict,
      },
    });

    expect(await view.findByText(/The collected evidence drifts/)).toHaveTextContent(
      "Tighten the entry point or the product will end up serving the wrong user.",
    );
    expect(view.getByText(/Most ideas need a body of data that does not exist yet/)).toHaveTextContent(
      "Plan how to collect, create, or obtain access to it before the product is useful.",
    );
    expect(view.getByText(/10 tools checked on the web/)).toHaveTextContent(
      "Early evidence is limited. Deep Research can validate it.",
    );
    expect(view.getByText(/gap in the collected evidence/)).toHaveTextContent(
      "published prices checked on the web show buyers already pay for tooling",
    );
    expect(view.getByText(/DaySmart Vet/)).toHaveTextContent(
      "Willingness-to-pay is not the primary risk.",
    );
    expect(await view.findByLabelText("Discovery take")).toHaveTextContent(
      "stored recommendation is not bound to exact current idea revisions",
    );
    expect(view.getByText(/Buyers here are small-business operators/)).toHaveTextContent(
      "They are price-aware but used to paying for tools that save time or win customers.",
    );
    expect(view.container.textContent).not.toMatch(
      /\bcorpus\b|cold-start|web-verified|paid wedge|Thin early signal|seed it|scrape it|\bwedge\b/i,
    );
  });

  it("rewrites exemplar data-source and critic prose before opening idea details", async () => {
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: [solution("Alpha Idea", {
          idea_id: "idea-alpha",
          idea_revision: 1,
          data_acquisition_notes: "Data route UNVERIFIED — could not confirm or refute a public source; verify obtainability before building. Evidence text was truncated mid-word.",
          critic_concern: "The mechanism parity check found overlap and data_access is unverified.",
        })],
        ideaPortfolioSummaryFingerprint: portfolioFingerprint([
          solution("Alpha Idea", { idea_id: "idea-alpha", idea_revision: 1 }),
        ]),
      },
    });

    await fireEvent.click(view.getByRole("button", { name: /^Review details for Alpha Idea/ }));
    await fireEvent.click(await view.findByRole("tab", { name: "All details" }));
    expect((await view.findAllByText(
      "Data access has not been verified. Confirm that the required source is available before building.",
    )).length).toBeGreaterThan(0);
    expect(view.getByText(/The feature overlap check found overlap/)).toHaveTextContent(
      "data access is unverified",
    );
    expect(view.container.textContent).not.toMatch(
      /Data route UNVERIFIED|mechanism parity|data_access|truncated mid-word/i,
    );
  });

  it("names the validated jobs that no surviving idea addresses", async () => {
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: THESIS_SOLUTIONS,
        ideaTheses: THESES,
        uncoveredFamilies: UNCOVERED,
      },
    });

    const section = await view.findByLabelText("Buyer-job coverage");
    expect(section).toHaveTextContent("3 buyer jobs examined · 2 theses · 1 with no idea in this pool");
    expect(view.getByText("1 validated buyer job above has no idea in this pool"))
      .toBeInTheDocument();
    expect(view.getByText("Teams manage DEA Form 222 and CSOS orders manually"))
      .toBeInTheDocument();
    // The pipeline's own sentence, not the `reason` enum token.
    expect(view.getByText("no generator cell was ever allocated to this family"))
      .toBeInTheDocument();
    expect(view.getByText("Evidence: 2 validated pain points")).toBeInTheDocument();
  });

  it("falls back to the flat ranked list when no partition is present", async () => {
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, solutions: THESIS_SOLUTIONS },
    });

    await waitFor(() => expect(view.getByLabelText("Select Order desk lead")).toBeInTheDocument());
    expect(view.getByLabelText("Select Order desk variant")).toBeInTheDocument();
    expect(view.getByLabelText("Select Billing capture")).toBeInTheDocument();
    expect(view.queryByText("Product thesis · 2 ideas")).toBeNull();
    expect(view.queryByLabelText("Buyer-job coverage")).toBeNull();
    expect(view.queryByLabelText("Ranked ideas")).toBeInTheDocument();
  });

  it("renders flat when a single thesis wraps every visible idea (no band, no coverage, no uncovered card)", async () => {
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: THESIS_SOLUTIONS,
        ideaTheses: [{
          ...THESES[0],
          members: members("Alpha Idea", "Beta Idea", "Gamma Idea"),
        }],
        uncoveredFamilies: UNCOVERED,
      },
    });

    await waitFor(() => expect(view.getByLabelText("Select Order desk lead")).toBeInTheDocument());
    expect(view.getByLabelText("Select Order desk variant")).toBeInTheDocument();
    expect(view.getByLabelText("Select Billing capture")).toBeInTheDocument();
    expect(view.queryByText("Controlled-order desk")).toBeNull();
    expect(view.queryByText("Product thesis · 3 ideas")).toBeNull();
    expect(view.queryByLabelText("Buyer-job coverage")).toBeNull();
    expect(view.queryByText(/validated buyer job/)).toBeNull();
    expect(view.queryByLabelText("Ranked ideas")).toBeInTheDocument();
  });

  it("still shows the thesis view when a single thesis leaves ideas ungrouped beside it", async () => {
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: THESIS_SOLUTIONS,
        ideaTheses: [THESES[0]],
      },
    });

    await waitFor(() => expect(view.getByText("Controlled-order desk")).toBeInTheDocument());
    expect(view.getByText("Not yet grouped")).toBeInTheDocument();
    const coverage = await view.findByLabelText("Buyer-job coverage");
    expect(coverage).toHaveTextContent("1 buyer job examined · 1 thesis");
  });

  it("hides the uncovered-jobs card when there are zero theses, even with uncovered families", async () => {
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: THESIS_SOLUTIONS,
        uncoveredFamilies: UNCOVERED,
      },
    });

    await waitFor(() => expect(view.getByLabelText("Select Order desk lead")).toBeInTheDocument());
    expect(view.queryByText(/validated buyer job/)).toBeNull();
    expect(view.queryByLabelText("Buyer-job coverage")).toBeNull();
    expect(view.queryByText("Teams manage DEA Form 222 and CSOS orders manually")).toBeNull();
  });

  it("survives a malformed partition without losing a candidate", async () => {
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: THESIS_SOLUTIONS,
        // A family whose ideas are all gone, and a live family that names an idea
        // twice — neither may drop or duplicate a selectable row.
        ideaTheses: [
          { ...THESES[0], members: members("Alpha Idea", "Alpha Idea") },
          { ...THESES[1], members: members("Deleted Idea") },
        ],
      },
    });

    await waitFor(() => expect(view.getByText("Controlled-order desk")).toBeInTheDocument());
    expect(view.queryByText("Consumption-to-billing capture")).toBeNull();
    expect(view.getByText("Not yet grouped")).toBeInTheDocument();
    expect(view.getAllByLabelText("Select Order desk lead")).toHaveLength(1);
    // The ungrouped bucket never collapses — every leftover idea stays selectable.
    expect(view.getByLabelText("Select Billing capture")).toBeInTheDocument();
    expect(view.getByLabelText("Select Order desk variant")).toBeInTheDocument();
  });

  it("shows ideas the partition does not reference, without a toggle to expand", async () => {
    // What a user sees straight after "Add another batch"/a seeded idea settles: the
    // pool grew but the partition is stale, so the new ideas land in "Not yet grouped".
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: [
          ...THESIS_SOLUTIONS,
          solution("Fresh Batch Idea", { idea_id: "idea-fresh", headline: "Just generated" }),
          solution("Seeded Idea", { idea_id: "idea-seeded", headline: "Your own idea" }),
        ],
        ideaTheses: [
          ...THESES,
          // A backend "unassigned" bucket is not a thesis — its members fall through.
          {
            family_id: "unassigned",
            display_label: "Unassigned",
            buyer: "",
            triggering_job: "",
            economic_outcome: "",
            members: members("Seeded Idea"),
            lead_idea_name: "",
            incumbent_status: "unknown",
            incumbent_vendors: [],
            fatal_assumptions: [],
          },
        ],
      },
    });

    await waitFor(() => expect(view.getByText("Not yet grouped")).toBeInTheDocument());
    expect(view.getByText("Added after grouping · 2 ideas")).toBeInTheDocument();
    expect(view.getByLabelText("Select Just generated")).toBeInTheDocument();
    expect(view.getByLabelText("Select Your own idea")).toBeInTheDocument();
    // Only the real thesis with a variant offers a toggle.
    expect(view.getAllByRole("button", { name: /variant/ })).toHaveLength(1);
  });

  it("tallies the GTM angles of a thesis's variants without claiming one for the job", async () => {
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: [
          solution("Alpha Idea", {
            idea_id: "idea-alpha",
            headline: "Order desk lead",
            winning_angle: "vertical_workflow",
          }),
          solution("Beta Idea", {
            idea_id: "idea-beta",
            headline: "Order desk variant",
            winning_angle: "vertical_workflow",
          }),
          solution("Gamma Idea", {
            idea_id: "idea-gamma",
            headline: "Order desk SEO play",
            winning_angle: "distribution_seo",
          }),
          // A row outside the thesis, so the thesis view stays meaningful (a single
          // thesis wrapping every visible idea is now suppressed as pure chrome).
          solution("Delta Idea", { idea_id: "idea-delta", headline: "Unrelated idea" }),
        ],
        ideaTheses: [{
          ...THESES[0],
          members: members("Alpha Idea", "Beta Idea", "Gamma Idea"),
        }],
      },
    });

    await waitFor(() => expect(view.getByText("Controlled-order desk")).toBeInTheDocument());
    expect(view.getByText("Angles across variants: Workflow ×2 · Distribution / SEO"))
      .toBeInTheDocument();
    // Per-variant chips stay in the rows (existing generation-lens chip), not the header.
    expect(view.getAllByText("Workflow")).toHaveLength(1);
    await fireEvent.click(view.getByRole("button", { name: "Show 2 variants" }));
    expect(view.getAllByText("Workflow")).toHaveLength(2);
    expect(view.getByText("Distribution / SEO")).toBeInTheDocument();
  });

  // The dispatch id of a batch this job actually ran. "New" is keyed on this and on
  // nothing else — see `newIdeaKeys`.
  const BATCH_OP_ID = "6823e26f-1b4d-4f0c-9a2c-000000000001";

  /** Put ONE settled batch in the ledger, the way a completed "Add another batch" does. */
  async function seedSettledBatch(operationId = BATCH_OP_ID, ordinal = 1) {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [{
        id: `batch-receipt-${operationId}`,
        gateStage: 5,
        role: "receipt",
        content: "Batch settled",
        patchJson: {
          kind: "ledger_event",
          version: 1,
          event: "regeneration_settled",
          patch: {},
          rows: [],
          operationId,
          batch: { ordinal, outcome: "completed", generatedCount: 2, addedCount: 2 },
        },
        createdAt: "2026-07-27T00:00:00.000Z",
      }],
      weakPool: false,
    } as never);
    await chatLedger.init("job-1");
  }

  /** Row titles of one card, lead first — the lead slot is the first row after the head. */
  const cardRowTitles = (view: { container: HTMLElement }, label: string) => {
    const card = [...view.container.querySelectorAll(".thesis-group")].find((node) =>
      node.querySelector(".thesis-label")?.textContent === label);
    return [...(card?.querySelectorAll(".opp-title") ?? [])].map((node) => node.textContent);
  };

  it("annotates a new batch inside the theses it joined, family first", async () => {
    await seedSettledBatch();
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: [
          ...THESIS_SOLUTIONS,
          solution("Delta Idea", {
            idea_id: "idea-delta",
            headline: "Order desk retry",
            generation_batch_ordinal: 1,
            generation_operation_id: BATCH_OP_ID,
          }),
          solution("Epsilon Idea", {
            idea_id: "idea-epsilon",
            headline: "Records retention",
            generation_batch_ordinal: 1,
            generation_operation_id: BATCH_OP_ID,
          }),
        ],
        ideaTheses: [
          { ...THESES[0], members: members("Alpha Idea", "Beta Idea", "Delta Idea") },
          THESES[1],
          {
            ...THESES[1],
            family_id: "fam-records",
            display_label: "Records retention desk",
            members: members("Epsilon Idea"),
            lead_idea_name: "Epsilon Idea",
          },
        ],
      },
    });

    await waitFor(() => expect(view.getByText("Records retention desk")).toBeInTheDocument());
    expect(view.getByText(
      "2 new ideas from your last request: 1 joined existing theses, 1 opened a new thesis.",
    )).toBeInTheDocument();
    // A batch that only added a variant to a standing thesis is NOT a new bet.
    expect(view.getAllByText("New thesis this batch")).toHaveLength(1);
    // The joiner is nested under its thesis, marked, and — since the user just paid for
    // it — visible without a click. The toggle is replaced by the reason it cannot close.
    expect(view.getByLabelText("Select Order desk retry")).toBeInTheDocument();
    expect(view.getByText("Expanded · 1 new in this batch")).toBeInTheDocument();
    expect(view.queryByRole("button", { name: /variants?$/ })).toBeNull();
    expect(view.getAllByText("New in this batch")).toHaveLength(2);
  });

  it("counts new ideas by the batch's dispatch id, never by a stamped ordinal", async () => {
    // REGRESSION: pools generated before the worker stamp was fixed carry FABRICATED
    // provenance (`generation_batch_ordinal: 1` with `generation_operation_id:
    // "expansion"`), and there is no backfill. Keying "new" on the ordinal counted that
    // idea as part of the batch — six chips over five real arrivals, one line above a
    // 100-credit commit, contradicting the analyst panel on the same screen.
    await seedSettledBatch();
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: [
          solution("Alpha Idea", {
            idea_id: "idea-alpha",
            headline: "Order desk lead",
            generation_batch_ordinal: 1,
            generation_operation_id: "expansion",
          }),
          solution("Beta Idea", { idea_id: "idea-beta", headline: "Order desk variant" }),
          solution("Gamma Idea", { idea_id: "idea-gamma", headline: "Billing capture" }),
          solution("Delta Idea", {
            idea_id: "idea-delta",
            headline: "Order desk retry",
            generation_batch_ordinal: 1,
            generation_operation_id: BATCH_OP_ID,
          }),
        ],
        ideaTheses: [
          { ...THESES[0], members: members("Alpha Idea", "Beta Idea", "Delta Idea") },
          THESES[1],
        ],
      },
    });

    await waitFor(() => expect(view.getByText("Controlled-order desk")).toBeInTheDocument());
    // One real arrival, one summary, one chip — the headline and the markers under it
    // read the same set, so they cannot disagree.
    expect(view.getByText("1 new idea from your last request: 1 joined existing theses."))
      .toBeInTheDocument();
    expect(view.getAllByText("New in this batch")).toHaveLength(1);
    expect(view.getByLabelText("Select Order desk retry")).toBeInTheDocument();
  });

  it("marks nothing new when no batch dispatch is known for the job", async () => {
    // Ledger empty (visitor view, a failed history load, a legacy pool): an ordinal on
    // its own is not evidence that this job ever ran a batch.
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: [
          ...THESIS_SOLUTIONS,
          solution("Delta Idea", {
            idea_id: "idea-delta",
            headline: "Order desk retry",
            generation_batch_ordinal: 1,
            generation_operation_id: "expansion",
          }),
        ],
        ideaTheses: [
          { ...THESES[0], members: members("Alpha Idea", "Beta Idea", "Delta Idea") },
          THESES[1],
        ],
      },
    });

    await waitFor(() => expect(view.getByText("Controlled-order desk")).toBeInTheDocument());
    expect(view.queryByText("New in this batch")).toBeNull();
    expect(view.queryByText(/new idea.? from your last request/)).toBeNull();
  });

  it("keeps the lead slot of a card a fresh arrival joins, however strong the arrival", async () => {
    // REGRESSION: the partition recomputes `lead_idea_name` after a batch, so a newcomer
    // that outscored the incumbent took the lead and pushed an already-reviewed idea into
    // a collapsed "Show 1 variant". Card order is frozen; the lead slot now is too — and
    // this holds on a cold mount, not just within one session.
    await seedSettledBatch();
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: [
          ...THESIS_SOLUTIONS,
          solution("Delta Idea", {
            idea_id: "idea-delta",
            headline: "Top scoring newcomer",
            market_fit_score: 0.99,
            technical_feasibility_score: 0.99,
            generation_batch_ordinal: 1,
            generation_operation_id: BATCH_OP_ID,
          }),
        ],
        ideaTheses: [
          THESES[0],
          {
            ...THESES[1],
            members: members("Delta Idea", "Gamma Idea"),
            lead_idea_name: "Delta Idea",
          },
        ],
      },
    });

    await waitFor(() =>
      expect(view.getByText("Consumption-to-billing capture")).toBeInTheDocument());
    // The idea the user already read still leads; the newcomer is the variant.
    expect(cardRowTitles(view, "Consumption-to-billing capture"))
      .toEqual(["Billing capture", "Top scoring newcomer"]);
    // And a variant nobody has seen yet is not hidden behind a toggle.
    expect(view.getByLabelText("Select Top scoring newcomer")).toBeInTheDocument();
  });

  it("keeps the lead slot when a batch lands into a card the user is already reading", async () => {
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, solutions: THESIS_SOLUTIONS, ideaTheses: THESES },
    });
    await waitFor(() => expect(view.getByText("Controlled-order desk")).toBeInTheDocument());
    expect(cardRowTitles(view, "Consumption-to-billing capture")).toEqual(["Billing capture"]);

    await seedSettledBatch();
    // Rerender the LIVE component — that is how a batch actually arrives.
    await view.rerender({
      ...baseProps,
      solutions: [
        ...THESIS_SOLUTIONS,
        solution("Delta Idea", {
          idea_id: "idea-delta",
          headline: "Top scoring newcomer",
          market_fit_score: 0.99,
          technical_feasibility_score: 0.99,
          generation_batch_ordinal: 1,
          generation_operation_id: BATCH_OP_ID,
        }),
      ],
      ideaTheses: [
        THESES[0],
        {
          ...THESES[1],
          members: members("Delta Idea", "Gamma Idea"),
          lead_idea_name: "Delta Idea",
        },
      ],
    });

    await waitFor(() =>
      expect(view.getByLabelText("Select Top scoring newcomer")).toBeInTheDocument());
    expect(cardRowTitles(view, "Consumption-to-billing capture"))
      .toEqual(["Billing capture", "Top scoring newcomer"]);
  });

  it("states why a held-open card cannot collapse instead of leaving a dead toggle", async () => {
    // REGRESSION: a card with a shortlisted variant is forced open, but the control still
    // read "Hide 1 variant" and clicking it did nothing at all.
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: THESIS_SOLUTIONS,
        ideaTheses: THESES,
        selectedSolutionIds: ["idea-beta"],
      },
    });

    await waitFor(() => expect(
      (view.getByLabelText("Deselect Order desk variant") as HTMLInputElement).checked,
    ).toBe(true));
    expect(view.queryByRole("button", { name: /variants?$/ })).toBeNull();
    expect(view.getByText("Expanded · 1 shortlisted here")).toBeInTheDocument();
  });

  const cardOrder = (view: { container: HTMLElement }) =>
    [...view.container.querySelectorAll(".thesis-label")].map((node) => node.textContent);

  it("opens with the strongest thesis first, not in payload order", async () => {
    // Payload order used to decide the board, so the first card a user saw could be the
    // weakest bet on the page. The card carrying the best idea leads.
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: [
          solution("Alpha Idea", { idea_id: "idea-alpha", headline: "Order desk lead" }),
          solution("Beta Idea", { idea_id: "idea-beta", headline: "Order desk variant" }),
          solution("Gamma Idea", {
            idea_id: "idea-gamma",
            headline: "Billing capture",
            market_fit_score: 0.99,
            technical_feasibility_score: 0.99,
          }),
        ],
        ideaTheses: THESES,
      },
    });

    await waitFor(() => expect(view.getByText("Controlled-order desk")).toBeInTheDocument());
    expect(cardOrder(view)).toEqual(["Consumption-to-billing capture", "Controlled-order desk"]);
  });

  it("keeps thesis order and nesting stable when a batch lands", async () => {
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, solutions: THESIS_SOLUTIONS, ideaTheses: THESES },
    });
    await waitFor(() => expect(view.getByText("Controlled-order desk")).toBeInTheDocument());
    expect(cardOrder(view)).toEqual(["Controlled-order desk", "Consumption-to-billing capture"]);

    // The batch idea outranks every original (score 0.99) — the board must not re-sort
    // around it, and the standing theses must keep their labels and their leads. This
    // rerenders the LIVE component, which is how a batch actually arrives; remounting
    // would test a fresh first-paint instead of the stability guarantee.
    await view.rerender({
      ...baseProps,
      solutions: [
        ...THESIS_SOLUTIONS,
        solution("Delta Idea", {
          idea_id: "idea-delta",
          headline: "Top scoring newcomer",
          market_fit_score: 0.99,
          technical_feasibility_score: 0.99,
          generation_batch_ordinal: 1,
        }),
      ],
      ideaTheses: [
        THESES[0],
        { ...THESES[1], members: members("Gamma Idea", "Delta Idea") },
      ],
    });
    await waitFor(() => expect(view.getByText("Controlled-order desk")).toBeInTheDocument());
    expect(cardOrder(view)).toEqual(["Controlled-order desk", "Consumption-to-billing capture"]);
    // Lead unchanged: the newcomer is a variant of the standing thesis, not its new face.
    expect(view.getByLabelText("Select Billing capture")).toBeInTheDocument();
    expect(view.queryByLabelText("Select Top scoring newcomer")).toBeNull();
  });

  it("appends a thesis that arrives with a later batch, however strong it is", async () => {
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, solutions: THESIS_SOLUTIONS, ideaTheses: THESES },
    });
    await waitFor(() => expect(view.getByText("Controlled-order desk")).toBeInTheDocument());

    await view.rerender({
      ...baseProps,
      solutions: [
        ...THESIS_SOLUTIONS,
        solution("Delta Idea", {
          idea_id: "idea-delta",
          headline: "Top scoring newcomer",
          market_fit_score: 0.99,
          technical_feasibility_score: 0.99,
          generation_batch_ordinal: 1,
        }),
      ],
      ideaTheses: [
        ...THESES,
        {
          ...THESES[1],
          family_id: "fam-new",
          display_label: "Newly opened thesis",
          members: members("Delta Idea"),
          lead_idea_name: "Delta Idea",
        },
      ],
    });
    await waitFor(() => expect(view.getByText("Newly opened thesis")).toBeInTheDocument());
    // Last, even though its only member outscores everything already on the board.
    expect(cardOrder(view)).toEqual([
      "Controlled-order desk",
      "Consumption-to-billing capture",
      "Newly opened thesis",
    ]);
  });

  it("drops the rank column on the grouped board and keeps it on the flat list", async () => {
    // Grouping replaced ranking as the organizing principle: a strong idea can sit in a
    // weak card, so a global "#" column reads 1, 7, 2, 3 whatever the card order is.
    const grouped = render(SelectionWorkbench, {
      props: { ...baseProps, solutions: THESIS_SOLUTIONS, ideaTheses: THESES },
    });
    await waitFor(() => expect(grouped.getByText("Controlled-order desk")).toBeInTheDocument());
    expect(grouped.container.querySelectorAll(".cell-rank")).toHaveLength(0);
    cleanup();

    // The flat fallback IS a ranking. These fixtures tie on score, so the shared
    // verdict formula gives every row rank 1 rather than inventing order from position.
    const flat = render(SelectionWorkbench, {
      props: { ...baseProps, solutions: THESIS_SOLUTIONS },
    });
    await waitFor(() => expect(flat.getByText("Order desk lead")).toBeInTheDocument());
    expect([...flat.container.querySelectorAll(".opp-row:not(.opp-row-head) .cell-rank")]
      .map((node) => node.textContent)).toEqual(["1", "1", "1"]);
  });

  it("omits the batch summary when no idea carries batch provenance", async () => {
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, solutions: THESIS_SOLUTIONS, ideaTheses: THESES },
    });

    await waitFor(() => expect(view.getByText("Controlled-order desk")).toBeInTheDocument());
    expect(view.queryByText(/new ideas from your last request/)).toBeNull();
    expect(view.queryByText("New in this batch")).toBeNull();
    expect(view.queryByText("New thesis this batch")).toBeNull();
  });

  it("omits the angle tally when ideas carry no angle", async () => {
    const view = render(SelectionWorkbench, {
      props: { ...baseProps, solutions: THESIS_SOLUTIONS, ideaTheses: THESES },
    });

    await waitFor(() => expect(view.getByText("Controlled-order desk")).toBeInTheDocument());
    expect(view.queryByText(/^Angle/)).toBeNull();
  });

  // END-TO-END CONTRACT PROOF. Every other test in this block hands the component
  // fixtures typed by the frontend — which is exactly how the feature shipped dead.
  // This one runs the real captured pipeline payload through the real reader, so a
  // producer-side rename puts the bands back on the floor here and nowhere else.
  it("renders thesis bands from the REAL pipeline payload, read off the report", async () => {
    const report = { idea_theses: pipelineIdeaTheses };
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: [
          solution("CountPad Vet", { idea_id: "i-1", headline: "Counts that reconcile" }),
          solution("Controlled Medication Dispense Closeout Ledger", {
            idea_id: "i-2",
            headline: "Dispense closeout ledger",
          }),
          solution("VetControlled Ledger", { idea_id: "i-3", headline: "Controlled ledger" }),
          solution("WitnessWire", { idea_id: "i-4", headline: "Witness capture" }),
          solution("CS Log Reconciliation Audit Kit", { idea_id: "i-5", headline: "Audit kit" }),
        ],
        ideaTheses: readIdeaTheses(report),
        uncoveredFamilies: readUncoveredFamilies(report),
      },
    });

    // One band per thesis, labelled and subtitled from the real buyer job.
    await waitFor(() => expect(view.getByText("Inventory Accuracy")).toBeInTheDocument());
    expect(view.getByText("Controlled-Drug Compliance")).toBeInTheDocument();
    expect(view.getByText(
      "Controlled Substance Compliance Officer · Keep controlled-drug logs complete and audit-ready · Regulatory compliance budget buys access-control and logging tools",
    )).toBeInTheDocument();
    expect(view.getByText("Product thesis · 3 ideas")).toBeInTheDocument();
    expect(view.getByText("Incumbent: occupied")).toBeInTheDocument();
    // Counts, not sentences-in-chips. The four flags on Controlled-Drug Compliance
    // belong to three different variants, so they are attributed rather than asserted
    // of the thesis — and the tournament's improvement directive is NOT called fatal.
    expect(view.getByRole("button", { name: "2 flagged assumptions" })).toBeInTheDocument();
    const compliance = view.getByRole("button", { name: "4 flagged assumptions" });
    await fireEvent.click(compliance);
    // The assumption is PIPELINE PROSE and is sanitised by `readIdeaTheses` on the way in,
    // so what renders is the buyer-facing reading — em dash gone. It is joined with a COMMA
    // rather than split into a new sentence: the tail is a relative clause modifying the
    // clause before it, and a period leaves "Which means the modal case…", a fragment.
    expect(view.getByText(
      "novelty: The anomaly detection is now the headline, but the core witness workflow still requires TWO people physically present at the tablet, which means the modal case (busy shift, only one other pe",
    )).toBeVisible();
    expect(view.getByText("Weak point")).toBeVisible();
    expect(view.getAllByText("WitnessWire").length).toBeGreaterThan(0);

    // Leads come from `lead_idea_name`; the other members nest as collapsed variants.
    expect(view.getByLabelText("Select Dispense closeout ledger")).toBeInTheDocument();
    expect(view.queryByLabelText("Select Controlled ledger")).toBeNull();

    // The partition's `unassigned` idea is not silently dropped.
    expect(view.getByText("Not yet grouped")).toBeInTheDocument();
    expect(view.getByLabelText("Select Audit kit")).toBeInTheDocument();

    // Coverage line and uncovered-jobs card, both of which never rendered before.
    expect(await view.findByLabelText("Buyer-job coverage"))
      .toHaveTextContent("3 buyer jobs examined · 2 theses · 1 with no idea in this pool");
    expect(view.getByText("System Integration")).toBeInTheDocument();
    expect(view.getByText(
      "we drafted at least one idea for this job, but no concept survived the review bar",
    )).toBeInTheDocument();
  });
});
