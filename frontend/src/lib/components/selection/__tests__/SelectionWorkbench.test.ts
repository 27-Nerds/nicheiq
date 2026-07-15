import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, fireEvent, cleanup, waitFor } from "@testing-library/svelte";
import SelectionWorkbench from "../SelectionWorkbench.svelte";
import { seedIdea, getStageCosts, ApiError, getChatHistory, streamChat } from "$lib/api";
import { chatLedger } from "$lib/stores/chatLedger.svelte";
import { chatPanel } from "$lib/stores/chatPanel.svelte";
import { creditTopUp } from "$lib/stores/creditTopUp.svelte";
import type { SolutionPreview } from "$lib/types/job";
import type { RuledOutFinding } from "$lib/types/report";

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
    selectSolution: vi.fn(),
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

    await findByText("The price changed — review the new cost and try again.");
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

    const { findByText, getByLabelText } = render(SelectionWorkbench, { props: baseProps });

    // chatLedger.hasPendingSeed only becomes true once the mocked history resolves.
    await waitFor(() => expect(chatLedger.hasPendingSeed).toBe(true));

    const regenBtn = (await findByText("Generate more ideas")).closest("button") as HTMLButtonElement;
    expect(regenBtn.disabled).toBe(true);

    const shortlistCheckbox = getByLabelText("Select Alpha Idea") as HTMLInputElement;
    expect(shortlistCheckbox.disabled).toBe(true);
  });

  it("with no pending seed and affordable credits, regenerate and shortlist stay enabled", async () => {
    const { findByText, getByLabelText } = render(SelectionWorkbench, { props: baseProps });

    const regenBtn = (await findByText("Generate more ideas")).closest("button") as HTMLButtonElement;
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
    const { findByText, queryByText } = render(SelectionWorkbench, {
      props: { ...baseProps, examinedRuledOut: RULED_OUT },
    });

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
    const { findByLabelText, findByRole, findByText } = render(SelectionWorkbench, {
      props: { ...baseProps, examinedRuledOut: RULED_OUT },
    });

    await fireEvent.click(await findByLabelText(
      "Review analysis for InvoiceChaser. This idea was ruled out.",
    ));
    await findByRole("dialog", { name: "Ruled-out analysis: InvoiceChaser" });
    await findByText("Automates invoice follow-up");
  });

  it("opens summary analysis for a legacy ruled-out finding without an idea payload", async () => {
    const { findByLabelText, findByRole } = render(SelectionWorkbench, {
      props: { ...baseProps, examinedRuledOut: RULED_OUT },
    });

    await fireEvent.click(await findByLabelText(
      "Review analysis for Manual reconciliation. This idea was ruled out.",
    ));
    const dialog = await findByRole("dialog", { name: "Ruled-out analysis: Manual reconciliation" });
    expect(dialog).toHaveTextContent("No buyer identified");
  });

  it("toggles the ruled-out list from the section header", async () => {
    const { findByRole, queryByText } = render(SelectionWorkbench, {
      props: { ...baseProps, examinedRuledOut: RULED_OUT },
    });

    const toggle = await findByRole("button", { name: "Examined and ruled out, 2 ideas" });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    await fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(queryByText("InvoiceChaser")).toBeNull();
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
    const { findByLabelText, findByText } = render(SelectionWorkbench, {
      props: { ...baseProps, examinedRuledOut: [generatedFinding] },
    });

    await findByText(
      "Concepts tied to researched pains that did not clear the final market-fit checks. Review why they were excluded.",
    );
    await fireEvent.click(await findByLabelText(
      "Review analysis for ReconcileFlow. This idea was ruled out.",
    ));
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
      "button", { name: "Open idea details for ProMatchDesk (CS2+Dota 2)" },
    ));
    await findByRole(
      "dialog", { name: "Solution details: ProMatchDesk (CS2+Dota 2)" },
    );
  });

  it("surfaces the final recommendation, marks its idea, and discloses supporting analysis", async () => {
    const { findByLabelText, findByText, queryByText } = render(SelectionWorkbench, {
      props: {
        ...baseProps,
        ideaPortfolioSummary: [
          "The pool has moderate market fit overall.",
          "Free incumbents make willingness to pay the central risk.",
          "Alpha Idea most deserves deeper validation because it has the clearest buyer.",
        ].join("\n\n"),
      },
    });

    const section = await findByLabelText("Analyst summary");
    const renderedNotes = section.querySelectorAll(".analyst-summary-text");
    expect(renderedNotes[0]).toHaveTextContent(
      "Alpha Idea most deserves deeper validation because it has the clearest buyer.",
    );

    const alphaRow = document.querySelector('[data-solution-name="Alpha Idea"]');
    const betaRow = document.querySelector('[data-solution-name="Beta Idea"]');
    expect(alphaRow).toHaveTextContent("Recommended");
    expect(betaRow).not.toHaveTextContent("Recommended");

    const disclosureLabel = await findByText("Read full analysis");
    const disclosure = disclosureLabel.closest("details");
    const toggle = disclosureLabel.closest("summary");
    expect(disclosure).not.toHaveAttribute("open");
    expect(queryByText("Hide full analysis")).toBeNull();
    expect(toggle).not.toBeNull();
    await fireEvent.click(toggle!);
    expect(disclosure).toHaveAttribute("open");
    await findByText("Hide full analysis");
    expect(queryByText("Read full analysis")).toBeNull();
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
      "button", { name: "Open idea details for InvoiceChaser" },
    ));
    await findByRole("dialog", { name: "Ruled-out analysis: InvoiceChaser" });
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
      "button", { name: "Open idea details for ProMatchDesk (CS2+Dota 2)" },
    ));
    await findByRole("dialog", { name: "Solution details: ProMatchDesk (CS2+Dota 2)" });
    expect(chatPanel.state).toBe("launcher");

    await fireEvent.click(await findByLabelText("Close details"));
    await waitFor(() => expect(chatPanel.state).toBe("expanded"));
    await findByRole("dialog", { name: "Analyst conversation" });
  });

  it("uses the same modal shell for idea detail and expanded chat", async () => {
    const { findByLabelText, findByRole } = render(SelectionWorkbench, { props: baseProps });

    await fireEvent.click(await findByLabelText(/^Review details for Alpha Idea\./));
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
