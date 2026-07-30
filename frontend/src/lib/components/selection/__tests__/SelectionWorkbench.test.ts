import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, fireEvent, cleanup, waitFor, within } from "@testing-library/svelte";
import { page } from "$app/state";
import { goto, pushState, replaceState } from "$app/navigation";
import SelectionWorkbench from "../SelectionWorkbench.svelte";
import { seedIdea, regenerateIdeas, getStageCosts, ApiError, createSelectionIdeaNarrowingProposal, getChatHistory, getSelectionChallenges, getSelectionConceptSets, getSelectionDecisionState, getSelectionExperiments, saveSelectionDecisionProfile, saveSelectionDraft, streamChat } from "$lib/api";
import { chatLedger } from "$lib/stores/chatLedger.svelte";
import { chatPanel } from "$lib/stores/chatPanel.svelte";
import { creditTopUp } from "$lib/stores/creditTopUp.svelte";
import type { SelectionDecisionProfile, SolutionPreview } from "$lib/types/job";
import type { RuledOutFinding } from "$lib/types/report";
import { SCORE_DEFINITIONS } from "$lib/utils/scoreDefinitions";

// SelectionWorkbench embeds a REAL ChatThread (the seed card lives there), which loads
// history on mount — stub the network-touching bits of $lib/api so mounting/submitting
// never fires a real fetch. Mirrors GateWorkbench.test.ts's convention for this family.
vi.mock("$lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("$lib/api")>();
  return {
    ...actual,
    seedIdea: vi.fn(),
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

const SOLUTIONS = [solution("Alpha Idea"), solution("Beta Idea")];

const STAGE_COSTS = { discovery: 5, deep_research: 15, landing_page: 5, regenerate_ideas: 2, seed_idea: 3 };

const baseProps = {
  jobId: "job-1",
  solutions: SOLUTIONS,
  creditBalance: 100,
  stageCosts: STAGE_COSTS,
  canRegenerate: true,
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

  it("opens a ranked idea from its shortened analyst-summary name", async () => {
    chatPanel.close();
    const proMatchDesk = solution("ProMatchDesk (CS2+Dota 2)");
    const { findByRole } = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: [proMatchDesk],
        examinedRuledOut: [],
        ideaPortfolioSummary: "ProMatchDesk is the strongest reporting workflow.",
      },
    });

    await fireEvent.click(await findByRole(
      "button", { name: /^ProMatchDesk \(CS2\+Dota 2\) ?, open details$/ },
    ));
    await findByRole(
      "dialog", { name: "Solution details: ProMatchDesk (CS2+Dota 2)" },
    );
  });

  it("keeps the verdict pull-quote visible, marks its idea, and files supporting notes in the collapsed appendix", async () => {
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

    // The discovery take stays on-screen above the ranked candidates.
    // (The idea-name chip appends an sr-only ", open details" hint to its text.)
    const verdict = await view.findByLabelText("Discovery take");
    expect(verdict).toHaveTextContent(
      /Alpha Idea.*most deserves deeper validation because it has the clearest buyer\./,
    );

    const alphaRow = document.querySelector('[data-solution-name="Alpha Idea"]');
    const betaRow = document.querySelector('[data-solution-name="Beta Idea"]');
    expect(alphaRow).toHaveTextContent("Recommended");
    expect(betaRow).not.toHaveTextContent("Recommended");

    // Supporting notes move to the discovery appendix: collapsed by default,
    // ONE plain meta line, zero counts omitted.
    const trigger = await view.findByRole("button", { name: /Discovery appendix/i });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(trigger).toHaveTextContent("2 analyst notes");
    expect(trigger).not.toHaveTextContent("feedback");
    expect(trigger).not.toHaveTextContent("ruled out");
    expect(view.getByText("Free incumbents make willingness to pay the central risk.")).not.toBeVisible();

    await fireEvent.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    const notes = await view.findByLabelText("Analyst notes");
    expect(notes).toHaveTextContent("The pool has moderate market fit overall.");
    expect(notes).toHaveTextContent("Free incumbents make willingness to pay the central risk.");
  });

  it("renders discovery-take idea links with the display title, not the internal codename", async () => {
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: [
          solution("AlphaIdeaCodename", { headline: "Alpha invoice chaser" }),
          solution("Beta Idea"),
        ],
        ideaPortfolioSummary: "AlphaIdeaCodename most deserves deeper validation.",
      },
    });

    const verdict = await view.findByLabelText("Discovery take");
    // (The link chip appends an sr-only ", open details" hint mid-sentence.)
    expect(verdict).toHaveTextContent(
      /Alpha invoice chaser.*most deserves deeper validation\./,
    );
    expect(verdict).not.toHaveTextContent("AlphaIdeaCodename");
  });

  it("badges only the explicit recommendation when one paragraph discusses every idea", async () => {
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
    expect(alphaRow).toHaveTextContent("Recommended");
    expect(betaRow).not.toHaveTextContent("Recommended");
    expect(document.querySelectorAll(".analyst-pick")).toHaveLength(1);
  });

  it("opens a ruled-out idea directly from the analyst summary", async () => {
    chatPanel.close();
    const { findByRole } = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        examinedRuledOut: RULED_OUT,
        ideaPortfolioSummary: "InvoiceChaser was examined but ruled out.",
      },
    });

    await fireEvent.click(await findByRole(
      "button", { name: /^InvoiceChaser ?, open details$/ },
    ));
    await findByRole("dialog", { name: "Ruled-out analysis: InvoiceChaser" });
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

  it("opens the exact candidate revision named by the server projection", async () => {
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
        reason: "Review the exact recommended candidate.",
        required: true,
        ideas: [{ ideaId: "idea-b", ideaRevision: 2, title: "Workflow-led path" }],
        lens: null,
        records: [],
      },
    } as never);
    const view = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        solutions: [
          solution("Alpha", { idea_id: "idea-a", idea_revision: 1, headline: "Audience-led path" }),
          solution("Beta", { idea_id: "idea-b", idea_revision: 2, headline: "Workflow-led path" }),
        ],
      },
    });

    await fireEvent.click(await view.findByRole("button", { name: "Review Workflow-led path" }));
    expect(await view.findByRole("dialog", { name: "Solution details: Workflow-led path" })).toBeInTheDocument();
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
      "http://localhost/jobs/job-1?keep=1&detailTab=detail&ideaId=idea-b&ideaRevision=4#opportunities",
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

  it("preserves unrelated query state while opening and closing exact details", async () => {
    page.url = new URL("http://localhost/jobs/job-1?keep=1#opportunities") as typeof page.url;
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
    expect(openedUrl.hash).toBe("#opportunities");

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
    page.url = new URL("http://localhost/jobs/job-1?addBatch=1#opportunities") as typeof page.url;
    const view = render(SelectionWorkbench, { props: baseProps });

    expect(await view.findByRole("dialog", { name: "Add another batch" })).toBeInTheDocument();
    expect(replaceState).toHaveBeenCalledWith(
      "/jobs/job-1#opportunities",
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

  it("keeps the opportunity-shape line visible while coverage disclosures file in the appendix", async () => {
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
    expect(view.getByText("Data caveats")).not.toBeVisible();

    await openAppendix(view);
    expect(view.getByText("Data caveats")).toBeVisible();
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
    // The row owns exactly one edit button; nothing else on the page duplicates it
    // (DecisionGuide no longer renders a founder-context entry of its own).
    expect(row.querySelectorAll("button")).toHaveLength(1);
    expect(view.getAllByRole("button", { name: "Edit build limits" })).toHaveLength(1);
    expect(view.queryByText("Your build limits")).not.toBeInTheDocument();
  });

  it("visitor view keeps the original inline analysis rendering (no appendix regrouping)", async () => {
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

    // No appendix, no founder row, no verdict pull-quote — the shared view is untouched.
    expect(view.queryByRole("button", { name: /Discovery appendix/i })).toBeNull();
    expect(view.queryByLabelText("Build limits summary")).toBeNull();
    expect(view.queryByLabelText("Discovery take")).toBeNull();

    // Analysis content stays inline and immediately accessible. (The idea-name
    // chip appends an sr-only ", open details" hint to its text.)
    expect(await view.findByLabelText("Research recommendation")).toHaveTextContent(
      /Alpha Idea.*most deserves deeper validation because it has the clearest buyer\./,
    );
    expect(view.getByText("Read full analysis")).toBeInTheDocument();
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

    expect(row).toHaveTextContent("Adversarial review: Killed");
    expect(row).not.toHaveTextContent("Incumbent: Evidence");
  });

  it("does not re-state column names as aria-labels on non-interactive cells", () => {
    const view = render(SelectionWorkbench, { props: baseProps });
    const table = view.getByRole("table", { name: "Ranked ideas" });

    for (const cell of within(table).getAllByRole("cell")) {
      expect(cell).not.toHaveAttribute("aria-label");
    }
  });

  it("reports aria-sort on the active column and 'none' on the others", () => {
    const view = render(SelectionWorkbench, { props: baseProps });
    const table = view.getByRole("table", { name: "Ranked ideas" });

    // Default sort is Score, descending.
    expect(
      within(table).getByRole("columnheader", { name: "Score /100" }),
    ).toHaveAttribute("aria-sort", "descending");

    for (const label of ["Market fit", "Feasibility", "Build time"]) {
      expect(
        within(table).getByRole("columnheader", { name: label }),
      ).toHaveAttribute("aria-sort", "none");
    }
  });

  it("flips aria-sort between descending and ascending when a column is re-activated", async () => {
    const view = render(SelectionWorkbench, { props: baseProps });
    const table = view.getByRole("table", { name: "Ranked ideas" });
    const header = () => within(table).getByRole("columnheader", { name: "Market fit" });

    // Activating an inactive column sorts it descending...
    await fireEvent.click(view.getByRole("button", { name: "Sort by Market fit" }));
    await waitFor(() => expect(header()).toHaveAttribute("aria-sort", "descending"));

    // ...and the button's name now announces what the next press will do.
    await fireEvent.click(
      view.getByRole("button", { name: "Sort by Market fit, ascending" }),
    );
    await waitFor(() => expect(header()).toHaveAttribute("aria-sort", "ascending"));

    await fireEvent.click(
      view.getByRole("button", { name: "Sort by Market fit, descending" }),
    );
    await waitFor(() => expect(header()).toHaveAttribute("aria-sort", "descending"));
  });

  it("uses aria-sort rather than aria-pressed to convey sort state", () => {
    const view = render(SelectionWorkbench, { props: baseProps });
    expect(view.getByRole("button", { name: "Sort by Score /100, ascending" })).not.toHaveAttribute(
      "aria-pressed",
    );
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
