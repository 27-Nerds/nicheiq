import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, fireEvent, cleanup, waitFor } from "@testing-library/svelte";
import ChatThread from "../ChatThread.svelte";
import { streamChat, getChatHistory, ApiError } from "$lib/api";
import type { ChatStreamEvent } from "$lib/api";
import { chatLedger } from "$lib/stores/chatLedger.svelte";
import { page } from "$app/state";
import {
  ANALYST_ACTION_NOT_HERE,
  ANALYST_ACTION_NOT_HERE_LINK,
  ANALYST_BILLING_HREF,
  ANALYST_ENTITLEMENT_UNAVAILABLE_NOTICE,
  ANALYST_LOCKED_LINK,
  ANALYST_LOCKED_NOTICE,
  ANALYST_PANEL_TITLE,
} from "../analystSurface";
import { rankedIdeasHref } from "$lib/selection/rankedIdeas";

// Chat agent tools v1.1 — ChatThread renders tool-call receipts (small muted mono ledger
// sub-entries) both LIVE while a turn streams (SSE `tool` events, backend chat.ts) and once
// PERSISTED (a reloaded history row's `toolCallsJson`). Stub the network-touching bits of
// $lib/api so mounting/sending never fires a real fetch — mirrors GateWorkbench.test.ts's
// convention for this component family.
vi.mock("$lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("$lib/api")>();
  return {
    ...actual,
    getChatHistory: vi.fn(() => Promise.resolve({ messages: [], weakPool: false })),
    streamChat: vi.fn(),
  };
});

/**
 * Matches one element by its FULL flattened text. `getByText`'s default matcher
 * reads only an element's direct text children, and the analyst notices now wrap
 * their destination in a real link, so the sentence spans several nodes.
 */
function flatText(expected: string) {
  return (_content: string, element: Element | null) =>
    element?.textContent?.replace(/\s+/g, " ").trim() === expected;
}

async function submitMessage(getByLabelText: (t: string) => HTMLElement, text: string) {
  const textarea = getByLabelText("Message the analyst") as HTMLTextAreaElement;
  await waitFor(() => expect(textarea.disabled).toBe(false));
  await fireEvent.input(textarea, { target: { value: text } });
  await fireEvent.submit(textarea.closest("form")!);
}

describe("ChatThread — tool receipts (chat agent tools v1.1)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // The ledger store is a page-scoped singleton that caches per jobId — reset it
    // so each test's mocked history actually loads.
    chatLedger.reset();
    vi.mocked(getChatHistory).mockResolvedValue({ messages: [], weakPool: false });
  });

  afterEach(() => {
    cleanup();
  });

  it("opens matched idea names in Markdown without rewriting links or code", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [{
        id: "idea-links",
        gateStage: 5,
        role: "assistant",
        content: "**ProMatchDesk** competes with [Alpha Idea](https://example.com) and `Beta Idea`.",
        patchJson: null,
        suggestionsJson: null,
        truncated: false,
        createdAt: "1",
      }],
      weakPool: false,
    } as never);
    const onOpenIdeaReference = vi.fn();
    const ideaReferences = [
      {
        id: "ranked:pro",
        label: "ProMatchDesk (CS2+Dota 2)",
        kind: "ranked" as const,
        solutionName: "ProMatchDesk (CS2+Dota 2)",
        aliases: ["ProMatchDesk"],
      },
      {
        id: "ranked:alpha",
        label: "Alpha Idea",
        kind: "ranked" as const,
        solutionName: "Alpha Idea",
        aliases: ["Alpha Idea"],
      },
      {
        id: "ranked:beta",
        label: "Beta Idea",
        kind: "ranked" as const,
        solutionName: "Beta Idea",
        aliases: ["Beta Idea"],
      },
    ];

    const { findByRole, findByText, queryByRole } = render(ChatThread, {
      props: {
        jobId: "job-idea-links",
        dock: "rail",
        ideaReferences,
        onOpenIdeaReference,
      },
    });

    // The visible idea name IS the accessible name (plus an sr-only affordance
    // hint). Matched aliases render the reference's canonical label, so the
    // sentence carries the full idea name when read by assistive tech.
    const ideaButton = await findByRole(
      "button", { name: /^ProMatchDesk \(CS2\+Dota 2\) ?, open details$/ },
    );
    await fireEvent.click(ideaButton);
    expect(onOpenIdeaReference).toHaveBeenCalledWith(ideaReferences[0]);
    expect(await findByRole("link", { name: "Alpha Idea" })).toHaveAttribute("href", "https://example.com");
    expect((await findByText("Beta Idea")).tagName).toBe("CODE");
    expect(queryByRole("button", { name: /^Alpha Idea ?, open details$/ })).toBeNull();
    expect(queryByRole("button", { name: /^Beta Idea ?, open details$/ })).toBeNull();
  });

  it("scrolls a loaded conversation to its latest message", async () => {
    const originalScrollTo = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "scrollTo");
    const scrollTo = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollTo", {
      configurable: true,
      value: scrollTo,
    });

    try {
      vi.mocked(getChatHistory).mockResolvedValue({
        messages: [
          {
            id: "m1",
            gateStage: 5,
            role: "assistant",
            content: "Latest answer.",
            patchJson: null,
            suggestionsJson: null,
            truncated: false,
            createdAt: "1",
          },
        ],
        weakPool: false,
      } as never);

      const { findByText } = render(ChatThread, { props: { jobId: "job-1", dock: "rail" } });
      await findByText("Latest answer.");
      await waitFor(() => expect(scrollTo).toHaveBeenCalled());
    } finally {
      if (originalScrollTo) {
        Object.defineProperty(HTMLElement.prototype, "scrollTo", originalScrollTo);
      } else {
        delete (HTMLElement.prototype as Partial<HTMLElement>).scrollTo;
      }
    }
  });

  it("scrolls to the latest message when the thread expands", async () => {
    const originalScrollTo = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "scrollTo");
    const scrollTo = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollTo", {
      configurable: true,
      value: scrollTo,
    });

    try {
      vi.mocked(getChatHistory).mockResolvedValue({
        messages: [
          {
            id: "m1",
            gateStage: 5,
            role: "assistant",
            content: "Latest answer.",
            patchJson: null,
            suggestionsJson: null,
            truncated: false,
            createdAt: "1",
          },
        ],
        weakPool: false,
      } as never);

      const { findByText, rerender } = render(ChatThread, {
        props: { jobId: "job-1", dock: "rail", focused: false },
      });
      await findByText("Latest answer.");
      await waitFor(() => expect(scrollTo).toHaveBeenCalled());
      scrollTo.mockClear();

      await rerender({ jobId: "job-1", dock: "rail", focused: true });

      await waitFor(() =>
        expect(scrollTo).toHaveBeenCalledWith(expect.objectContaining({ behavior: "auto" })),
      );
    } finally {
      if (originalScrollTo) {
        Object.defineProperty(HTMLElement.prototype, "scrollTo", originalScrollTo);
      } else {
        delete (HTMLElement.prototype as Partial<HTMLElement>).scrollTo;
      }
    }
  });

  it("renders a live tool receipt while streaming — before the final answer arrives", async () => {
    let onEvent: ((evt: ChatStreamEvent) => void) | undefined;
    let resolveStream: () => void = () => {};
    const streamPromise = new Promise<void>((resolve) => {
      resolveStream = resolve;
    });
    vi.mocked(streamChat).mockImplementation(async (_jobId, _message, opts) => {
      onEvent = opts.onEvent;
      return streamPromise;
    });

    const { getByLabelText, findByText, queryByText } = render(ChatThread, {
      props: { jobId: "job-1", dock: "rail" },
    });

    await submitMessage(getByLabelText, "what evidence backs the late-invoices pain?");

    expect(onEvent).toBeTruthy();
    // Tool receipt arrives before any answer text — the pending block should show it
    // immediately, with no final content yet.
    onEvent!({ type: "tool", label: 'Checked evidence for "Chasing late invoices"' });
    await findByText('Checked evidence for "Chasing late invoices"');
    expect(queryByText("People said they spend hours chasing late invoices.")).toBeNull();

    // Final streamed answer, then done — the receipt should still be visible, now as
    // part of the persisted message.
    onEvent!({ type: "token", delta: "People said they spend hours chasing late invoices." });
    onEvent!({
      type: "done",
      message: {
        id: "asst-1",
        role: "assistant",
        content: "People said they spend hours chasing late invoices.",
        patchJson: null,
        toolCallsJson: [
          { name: "get_pain_evidence", args: { pain_title: "Chasing late invoices" }, label: 'Checked evidence for "Chasing late invoices"' },
        ],
        createdAt: "2026-07-12T00:00:00.000Z",
      },
    });
    resolveStream();

    await findByText("People said they spend hours chasing late invoices.");
    expect(await findByText('Checked evidence for "Chasing late invoices"')).toBeTruthy();
  });

  it("renders persisted toolCallsJson receipts from chat history on reload", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [
        {
          id: "m1",
          gateStage: 5,
          role: "assistant",
          content: "Here's what the evidence shows.",
          patchJson: null,
          toolCallsJson: [
            { name: "get_pain_evidence", args: { pain_title: "Chasing late invoices" }, label: 'Checked evidence for "Chasing late invoices"' },
          ],
          truncated: false,
          createdAt: "2026-07-12T00:00:00.000Z",
        },
      ],
      weakPool: false,
    });

    const { findByText } = render(ChatThread, { props: { jobId: "job-1", dock: "rail" } });

    await findByText('Checked evidence for "Chasing late invoices"');
    await findByText("Here's what the evidence shows.");
  });

  it("keeps ordered and unordered Markdown list markers visible inside the transcript", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [
        {
          id: "m1",
          gateStage: 5,
          role: "assistant",
          content: "Sources:\n\n- Liquipedia\n- HLTV\n\nSteps:\n\n1. Mirror events\n2. Normalize teams",
          patchJson: null,
          truncated: false,
          createdAt: "1",
        },
      ],
      weakPool: false,
    } as never);

    const { findByText, container } = render(ChatThread, {
      props: { jobId: "job-1", dock: "rail", focused: true },
    });

    await findByText("Liquipedia");
    const unordered = container.querySelector(".entry-prose ul");
    const ordered = container.querySelector(".entry-prose ol");
    expect(unordered).toBeInstanceOf(HTMLUListElement);
    expect(ordered).toBeInstanceOf(HTMLOListElement);
    expect(getComputedStyle(unordered!).listStyleType).toBe("disc");
    expect(getComputedStyle(ordered!).listStyleType).toBe("decimal");
    expect(getComputedStyle(unordered!).paddingInlineStart).not.toBe("0px");
    expect(getComputedStyle(ordered!).paddingInlineStart).not.toBe("0px");
  });

  it("hands the draft back when the message never reaches the server", async () => {
    vi.mocked(streamChat).mockRejectedValueOnce(new Error("network down"));

    const { getByLabelText, findByText, queryByText } = render(ChatThread, {
      props: { jobId: "job-1", dock: "rail" },
    });

    await submitMessage(getByLabelText, "what about pricing?");

    await findByText("The analyst couldn't respond. Try again.");
    // The typed text is restored (it was cleared optimistically) and the phantom
    // turn is retracted — a failed send must not eat the user's words.
    const textarea = getByLabelText("Message the analyst") as HTMLTextAreaElement;
    expect(textarea.value).toBe("what about pricing?");
    expect(queryByText("what about pricing?", { selector: ".entry-plain" })).toBeNull();
  });

  it("explains a 409 as the checkpoint moving on, and keeps the draft", async () => {
    vi.mocked(streamChat).mockRejectedValueOnce(new ApiError("stale", 409));

    const { getByLabelText, findByText } = render(ChatThread, {
      props: { jobId: "job-1", dock: "rail" },
    });

    await submitMessage(getByLabelText, "exclude the betting pain");

    await findByText("This checkpoint moved on. Your message wasn't sent.");
    expect((getByLabelText("Message the analyst") as HTMLTextAreaElement).value).toBe(
      "exclude the betting pain",
    );
  });

  it("counts turns across the WHOLE run — the cap is per job, not per checkpoint", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [
        { id: "a", gateStage: 1, role: "user", content: "g1", patchJson: null, truncated: false, createdAt: "1" },
        { id: "b", gateStage: 4, role: "user", content: "g2", patchJson: null, truncated: false, createdAt: "2" },
        { id: "c", gateStage: 5, role: "user", content: "g3", patchJson: null, truncated: false, createdAt: "3" },
      ],
      weakPool: false,
    });

    const { findByLabelText } = render(ChatThread, { props: { jobId: "job-1", dock: "rail" } });

    // This thread only shows the G3 segment, but the counter reports the enforced
    // global budget (3 turns spent), not the 1 turn visible here.
    await findByLabelText("Questions this run · 3 of 30 used");
  });

  it("shows the analyst's own follow-ups over the caller's state-derived fallbacks", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [
        {
          id: "m1",
          gateStage: 5,
          role: "assistant",
          content: "Rankings are close between the top two.",
          patchJson: null,
          suggestionsJson: ["What separates the top two?"],
          truncated: false,
          createdAt: "1",
        },
      ],
      weakPool: false,
    } as never);

    const { findByText, getByRole, queryByText } = render(ChatThread, {
      props: { jobId: "job-1", dock: "rail", starters: ["Which is easiest to build?"] },
    });

    // The analyst knows what it just said and what it left open — its chips win.
    const followUp = await findByText("What separates the top two?");
    expect(getByRole("log", { name: "Conversation" }).contains(followUp)).toBe(true);
    expect(queryByText("Which is easiest to build?")).toBeNull();
  });

  it("uses contextual fallbacks for legacy answers without stored follow-ups", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [
        {
          id: "u1",
          gateStage: 5,
          role: "user",
          content: "Can you analyze my fantasy card game idea?",
          patchJson: null,
          truncated: false,
          createdAt: "0",
        },
        {
          id: "m1",
          gateStage: 5,
          role: "assistant",
          content: "Here's the pool.",
          patchJson: null,
          suggestionsJson: null,
          truncated: false,
          createdAt: "1",
        },
      ],
      weakPool: false,
    } as never);

    const { findByText, queryByText } = render(ChatThread, {
      props: { jobId: "job-1", dock: "rail", starters: ["Which is easiest to build?"] },
    });

    await findByText("Here's the pool.");
    await findByText("Go deeper on this answer");
    expect(queryByText("Which is easiest to build?")).toBeNull();
  });

  it("uses caller starters only before the conversation begins", async () => {
    const { findByText } = render(ChatThread, {
      props: { jobId: "job-1", dock: "rail", starters: ["Which is easiest to build?"] },
    });

    await findByText("Which is easiest to build?");
  });

  it("does not render a tool-receipts list for a plain-text turn with no tool calls", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [
        {
          id: "m1",
          gateStage: 5,
          role: "assistant",
          content: "The market fit here is moderate.",
          patchJson: null,
          toolCallsJson: null,
          truncated: false,
          createdAt: "2026-07-12T00:00:00.000Z",
        },
      ],
      weakPool: false,
    });

    const { findByText, container } = render(ChatThread, { props: { jobId: "job-1", dock: "rail" } });

    await findByText("The market fit here is moderate.");
    expect(container.querySelector(".tool-receipts")).toBeNull();
  });
});

// BLOCKER fix: an in-flight stream for one job must never survive a navigation to
// another job's page. SvelteKit can update this component's `jobId` prop in place
// across a route change rather than destroying/recreating it, so both "the component
// unmounts" and "jobId changes on the live instance" have to abort the stream — and
// even a late callback that sneaks past the abort must be dropped by the ledger, not
// appended into whatever job is now on screen.
describe("ChatThread — stream lifecycle guards (wrong-job ledger contamination)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chatLedger.reset();
    vi.mocked(getChatHistory).mockResolvedValue({ messages: [], weakPool: false });
  });

  afterEach(() => {
    cleanup();
  });

  it("aborts the in-flight stream when the component is unmounted", async () => {
    let capturedSignal: AbortSignal | undefined;
    vi.mocked(streamChat).mockImplementation(async (_jobId, _message, opts) => {
      capturedSignal = opts.signal;
      return new Promise<void>(() => {}); // never resolves on its own — an in-flight stream
    });

    const { getByLabelText, unmount } = render(ChatThread, { props: { jobId: "job-1", dock: "rail" } });
    await submitMessage(getByLabelText, "what's the market fit?");

    expect(capturedSignal?.aborted).toBe(false);
    unmount();
    expect(capturedSignal?.aborted).toBe(true);
  });

  it("aborts the in-flight stream when jobId changes without a remount", async () => {
    let capturedSignal: AbortSignal | undefined;
    vi.mocked(streamChat).mockImplementation(async (_jobId, _message, opts) => {
      capturedSignal = opts.signal;
      return new Promise<void>(() => {});
    });

    const { getByLabelText, rerender } = render(ChatThread, { props: { jobId: "job-1", dock: "rail" } });
    await submitMessage(getByLabelText, "what's the market fit?");
    expect(capturedSignal?.aborted).toBe(false);

    vi.mocked(getChatHistory).mockResolvedValue({ messages: [], weakPool: false });
    await rerender({ jobId: "job-2", dock: "rail" });

    expect(capturedSignal?.aborted).toBe(true);
  });

  it("drops a stale assistant reply that resolves for job A after the thread moved to job B", async () => {
    let onEventA: ((evt: ChatStreamEvent) => void) | undefined;
    vi.mocked(streamChat).mockImplementation(async (_jobId, _message, opts) => {
      onEventA = opts.onEvent;
      return new Promise<void>(() => {});
    });

    const { getByLabelText, rerender, queryByText } = render(ChatThread, {
      props: { jobId: "job-A", dock: "rail" },
    });
    await submitMessage(getByLabelText, "what's the market fit?");
    expect(onEventA).toBeTruthy();

    // Navigate to job B before job A's stream resolves.
    vi.mocked(getChatHistory).mockResolvedValue({ messages: [], weakPool: false });
    await rerender({ jobId: "job-B", dock: "rail" });
    await waitFor(() => expect(chatLedger.jobId).toBe("job-B"));

    // The late event for job A's turn arrives anyway — the exact race: the fetch had
    // already buffered this chunk before abort() took effect.
    onEventA!({
      type: "done",
      message: {
        id: "asst-A",
        role: "assistant",
        content: "job A's answer",
        patchJson: null,
        createdAt: "2026-07-13T00:00:00.000Z",
      },
    });

    // It must never land in the ledger now backing job B.
    expect(queryByText("job A's answer")).toBeNull();
  });
});

// Priced seed card (plans/eager-meandering-feather.md Phase 6/8) — the user-composed
// idea seed gets its own card (never the generic before→after diff table), priced from
// stage-costs' flat `seed_idea`, with terminal state derived from chatLedger.seedOutcome
// (durable receipts), never a parallel client store.
//
// Each test builds its OWN message id via `seedMessage()` rather than sharing one
// constant: "Keep as is" dismissals persist to localStorage keyed by message id
// (chatLedger.svelte.ts's DISMISSED_KEY_PREFIX), and every test here reuses jobId
// "job-1" — a shared id would leak a dismissal from one test into the next.
function seedMessage(id: string) {
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
const SEED_MESSAGE = seedMessage("asst-seed-base");

function synthesisMessage(id: string) {
  return {
    id,
    gateStage: 5,
    role: "assistant" as const,
    content: "Here is one variant to consider.",
    patchJson: {
      kind: "idea_synthesis" as const,
      operation: "combine" as const,
      proposedTitle: "Agency signal desk",
      proposedBrief: "Combines change alerts with a client-ready briefing.",
      changeSummary: "Joins two workflows for the same agency buyer.",
      rationale: "The sources solve adjacent parts of one recurring job.",
      parents: [
        { ideaId: "idea-1", ideaRevision: 1, solutionName: "Change monitor", contribution: "Keep the alerting." },
      ],
      evidence: {
        sourceAnchors: [{ ideaId: "idea-1", ideaRevision: 1, candidateSnapshotSha256: "a".repeat(64) }],
        requiresValidation: ["Validate that one buyer needs both capabilities."],
      },
      newAssumptions: ["Agencies own both workflows."],
    },
    truncated: false,
    createdAt: "2026-07-16T00:00:00.000Z",
  };
}

/** A durable `seed_settled` receipt, shaped exactly like `buildSeedEnvelope`
 *  (backend/src/utils/ledgerEvents.ts:168-253) writes it.
 *
 *  Two identity carriers, and they are NOT interchangeable:
 *  - `evaluationId` on the ENVELOPE is the dispatch id. Every settled receipt the
 *    server writes today passes one (workers.ts:2354/2532, dispatchService.ts:256,
 *    jobService.ts:675, paidPoolRecoveryService.ts:218/523), so this is the
 *    production carrier for BOTH plain seeds and synthesis.
 *  - `idea.evaluation_id` on the RESULT is stamped only by exact synthesis
 *    (`stampSynthesizedIdeaIdentity`, ideaIdentity.ts:108-121). A plain user seed
 *    goes through `stampNewIdeaIdentities` -> `withIdentity` (ideaIdentity.ts:39-45),
 *    which adds ONLY `idea_id`/`idea_revision`.
 *  The builder never copies `dispatch_id` onto the result summary at all, so no
 *  fixture may hand-write one. */
function seedSettledReceipt(
  sourceMessageId: string,
  outcome: "accepted" | "demoted",
  idea?: Record<string, unknown>,
  evaluationId?: string,
) {
  return {
    id: `${sourceMessageId}-receipt`,
    gateStage: 5,
    role: "receipt" as const,
    content: "",
    patchJson: {
      kind: "ledger_event" as const,
      version: 1,
      event: "seed_settled" as const,
      outcome,
      patch: {},
      rows: [],
      sourceMessageId,
      ...(evaluationId ? { evaluationId } : {}),
      ...(idea ? { idea } : {}),
    },
    truncated: false,
    createdAt: "2026-07-13T00:00:01.000Z",
  };
}

describe("ChatThread — priced idea-seed card", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chatLedger.reset();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders the idea, evaluation anchor, rationale, and price for an undecided seed", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({ messages: [SEED_MESSAGE], weakPool: false } as never);

    const { findByText } = render(ChatThread, { props: { jobId: "job-1", dock: "rail", seedCost: 3 } });

    await findByText("Review your idea");
    await findByText("A tool that auto-reconciles freelance invoices");
    await findByText("Evaluation anchor");
    await findByText("Chasing late invoices");
    await findByText("Matches a validated pain with no direct incumbent");
    await findByText("Evaluate my idea");
    await findByText("3");
    await findByText("Dismiss");
  });

  it("hides follow-ups while the idea awaits a decision, then restores them after dismissal", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [
        {
          id: "user-seed-review",
          gateStage: 5,
          role: "user" as const,
          content: "Analyze my idea.",
          patchJson: null,
          truncated: false,
          createdAt: "2026-07-13T00:00:00.000Z",
        },
        seedMessage("asst-seed-review"),
      ],
      weakPool: false,
    } as never);

    const { findByText, queryByText } = render(ChatThread, {
      props: { jobId: "job-1", dock: "rail", seedCost: 3 },
    });

    await findByText("Evaluate my idea");
    expect(queryByText("Continue exploring")).toBeNull();

    await fireEvent.click(await findByText("Dismiss"));
    await findByText("Continue exploring");
  });

  it("disables Evaluate and explains when the price hasn't loaded", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({ messages: [SEED_MESSAGE], weakPool: false } as never);

    // `onSeedSubmit` is what makes "the price is still loading" the true explanation:
    // only a host that can evaluate ever waits for a price. Without it the card says
    // which screen owns the action instead (see the D15 case at the end of this file).
    const { findByText } = render(ChatThread, {
      props: { jobId: "job-1", dock: "rail", seedCost: null, onSeedSubmit: vi.fn() },
    });

    const evaluateBtn = (await findByText("Evaluate my idea")).closest("button") as HTMLButtonElement;
    expect(evaluateBtn.disabled).toBe(true);
    await findByText("Price hasn't loaded yet. Try again in a moment.");
  });

  it("calls onSeedSubmit with the patch and the proposing message id on Evaluate", async () => {
    const msg = seedMessage("asst-seed-submit");
    vi.mocked(getChatHistory).mockResolvedValue({ messages: [msg], weakPool: false } as never);
    const onSeedSubmit = vi.fn();

    const { findByText } = render(ChatThread, {
      props: { jobId: "job-1", dock: "rail", seedCost: 3, onSeedSubmit },
    });

    await fireEvent.click(await findByText("Evaluate my idea"));

    expect(onSeedSubmit).toHaveBeenCalledTimes(1);
    expect(onSeedSubmit).toHaveBeenCalledWith(msg.patchJson, "asst-seed-submit");
  });

  it("disables Evaluate/Dismiss while a pool mutation (applying) is in flight", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [seedMessage("asst-seed-applying")],
      weakPool: false,
    } as never);

    const { findByText } = render(ChatThread, {
      props: { jobId: "job-1", dock: "rail", seedCost: 3, applying: true },
    });

    const evaluateBtn = (await findByText("Evaluate my idea")).closest("button") as HTMLButtonElement;
    const dismissBtn = (await findByText("Dismiss")).closest("button") as HTMLButtonElement;
    expect(evaluateBtn.disabled).toBe(true);
    expect(dismissBtn.disabled).toBe(true);
  });

  it("dismissing the card removes it (no re-arm) — same 'Keep as is' mechanism as other patches", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [seedMessage("asst-seed-dismiss")],
      weakPool: false,
    } as never);

    const { findByText, queryByText } = render(ChatThread, { props: { jobId: "job-1", dock: "rail", seedCost: 3 } });

    await fireEvent.click(await findByText("Dismiss"));

    expect(queryByText("Evaluate my idea")).toBeNull();
    expect(queryByText("A tool that auto-reconciles freelance invoices")).toBeNull();
  });

  it("renders a durable 'pending' outcome as Evaluating, with no Evaluate/Dismiss buttons", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [
        seedMessage("asst-seed-pending"),
        {
          id: "seed-receipt-1",
          gateStage: 5,
          role: "receipt" as const,
          content: "",
          patchJson: {
            kind: "ledger_event" as const,
            version: 1,
            event: "seed_submitted" as const,
            patch: {},
            rows: [],
            sourceMessageId: "asst-seed-pending",
          },
          truncated: false,
          createdAt: "2026-07-13T00:00:01.000Z",
        },
      ],
      weakPool: false,
    } as never);

    const { container, findByText, queryByText } = render(ChatThread, {
      props: { jobId: "job-1", dock: "rail", seedCost: 3 },
    });

    await findByText("Evaluating your idea…");
    const pendingCard = container.querySelector(".seed-card--pending");
    expect(pendingCard).toHaveAttribute("aria-busy", "true");
    expect(pendingCard?.querySelector(".seed-card-head")).toHaveAttribute("aria-live", "polite");
    expect(queryByText("Evaluate my idea")).toBeNull();
    expect(queryByText("Dismiss")).toBeNull();
  });

  it("renders an accepted seed with its evaluated result and candidate link", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [
        seedMessage("asst-seed-accepted"),
        {
          id: "seed-receipt-2",
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
            sourceMessageId: "asst-seed-accepted",
            idea: {
              solution_name: "PatchZero",
              short_description: "Finds missed esports reporting leads.",
              market_fit_score: 0.45,
            },
          },
          truncated: false,
          createdAt: "2026-07-13T00:00:01.000Z",
        },
      ],
      weakPool: false,
    } as never);

    const { findByText, queryByText, getByRole } = render(ChatThread, { props: { jobId: "job-1", dock: "rail", seedCost: 3 } });

    await findByText("Evaluation complete. Added to ranked ideas.");
    expect(queryByText("PatchZero")).not.toBeNull();
    expect(queryByText("Market fit 45%")).not.toBeNull();
    expect(getByRole("link", { name: /view full candidate details/i }))
      .toHaveAttribute("href", rankedIdeasHref("job-1"));
    expect(queryByText("Evaluate my idea")).toBeNull();
  });

  it("renders a durable 'demoted' outcome with the market-fit-bar copy", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [
        seedMessage("asst-seed-demoted"),
        {
          id: "seed-receipt-3",
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
            sourceMessageId: "asst-seed-demoted",
          },
          truncated: false,
          createdAt: "2026-07-13T00:00:01.000Z",
        },
      ],
      weakPool: false,
    } as never);

    const { findByText } = render(ChatThread, { props: { jobId: "job-1", dock: "rail", seedCost: 3 } });

    await findByText("We tested your idea. It didn't clear the market-fit bar.");
  });

  it("renders a synthesis proposal as an unevaluated variant requiring explicit approval", async () => {
    const proposal = {
      kind: "idea_synthesis" as const,
      operation: "combine" as const,
      proposedTitle: "Agency signal desk",
      proposedBrief: "Combines change alerts with a client-ready briefing.",
      changeSummary: "Joins two workflows for the same agency buyer.",
      rationale: "The sources solve adjacent parts of one recurring job.",
      parents: [
        {
          ideaId: "idea-1",
          ideaRevision: 1,
          solutionName: "Change monitor",
          contribution: "Keep the alerting mechanism.",
        },
        {
          ideaId: "idea-2",
          ideaRevision: 1,
          solutionName: "Briefing desk",
          contribution: "Keep the client-ready summary.",
        },
      ],
      evidence: {
        sourceAnchors: [
          { ideaId: "idea-1", ideaRevision: 1, candidateSnapshotSha256: "a".repeat(64) },
          { ideaId: "idea-2", ideaRevision: 1, candidateSnapshotSha256: "b".repeat(64) },
        ],
        requiresValidation: ["Validate that one buyer needs both capabilities."],
      },
      newAssumptions: ["Agencies own both workflows."],
    };
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [{
        id: "asst-synthesis",
        gateStage: 5,
        role: "assistant",
        content: "Here is one variant to consider.",
        patchJson: proposal,
        suggestionsJson: null,
        truncated: false,
        createdAt: "2026-07-16T00:00:00.000Z",
      }],
      weakPool: false,
    } as never);
    const onSeedSubmit = vi.fn();

    const { findByText, getByRole } = render(ChatThread, {
      props: {
        jobId: "job-synthesis",
        dock: "rail",
        seedCost: 3,
        onSeedSubmit,
      },
    });

    await findByText("Combine candidate");
    await findByText("Agency signal desk");
    await findByText("The source candidates stay unchanged. Their scores do not carry over to this variant.");
    const evaluate = getByRole("button", { name: /evaluate variant/i });
    await fireEvent.click(evaluate);
    expect(onSeedSubmit).toHaveBeenCalledWith(proposal, "asst-synthesis");
    expect(getByRole("button", { name: "Dismiss" })).toBeTruthy();
  });

  it("routes a selection copilot card through its review callback without applying a patch", async () => {
    const action = {
      kind: "selection_copilot_action" as const,
      action: "prefill" as const,
      target: "decision_profile" as const,
      ideas: [],
      values: { weeklyTime: "HOURS_10_20" },
      rationale: "Your stated availability should be reviewed in the decision context.",
      caveats: ["Confirm this still reflects your schedule."],
    };
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [{
        id: "copilot-profile",
        gateStage: 5,
        role: "assistant",
        content: "I prepared a draft for review.",
        patchJson: action,
        suggestionsJson: null,
        truncated: false,
        createdAt: "2026-07-16T00:00:00.000Z",
      }],
      weakPool: false,
    } as never);
    const onCopilotAction = vi.fn().mockReturnValue({ ok: true, message: "Draft opened." });
    const onApplyPatch = vi.fn();

    const view = render(ChatThread, {
      props: { jobId: "job-copilot", dock: "rail", onCopilotAction, onApplyPatch },
    });

    expect(await view.findByText("Review only")).toBeInTheDocument();
    expect(view.getByText("Nothing has been changed. The existing form or shortlist confirmation is the only place that can save this.")).toBeInTheDocument();
    await fireEvent.click(view.getByRole("button", { name: "Review draft" }));
    expect(onCopilotAction).toHaveBeenCalledWith(action, "copilot-profile");
    expect(onApplyPatch).not.toHaveBeenCalled();
  });

  it("does not render live selection copilot actions in a read-only transcript", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [{
        id: "copilot-readonly",
        gateStage: 5,
        role: "assistant",
        content: "Review this candidate.",
        patchJson: {
          kind: "selection_copilot_action",
          action: "open",
          target: "candidate",
          ideas: [{ ideaId: "idea-1", ideaRevision: 2, solutionName: "Signal desk" }],
          rationale: "It has the strongest current evidence.",
          caveats: [],
        },
        suggestionsJson: null,
        truncated: false,
        createdAt: "2026-07-16T00:00:00.000Z",
      }],
      weakPool: false,
    } as never);

    const view = render(ChatThread, {
      props: { jobId: "job-copilot-readonly", dock: "rail", readOnly: true },
    });

    expect(await view.findByText("This action is available only in the owner workspace.")).toBeInTheDocument();
    expect(view.queryByRole("button", { name: "Open candidate" })).not.toBeInTheDocument();
    expect(view.queryByLabelText("Message the analyst")).not.toBeInTheDocument();
  });

  it("keeps the transcript visible but blocks the composer during an active operation", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [{
        id: "operation-history",
        gateStage: 5,
        role: "assistant",
        content: "Your saved comparison is still available.",
        patchJson: null,
        suggestionsJson: null,
        truncated: false,
        createdAt: "2026-07-16T00:00:00.000Z",
      }],
      weakPool: false,
    } as never);

    const view = render(ChatThread, {
      props: {
        jobId: "job-operation-active",
        dock: "rail",
        blocked: true,
        blockedTitle: "Adding another batch",
        blockedDetail: "The transcript remains available. New questions unlock when this operation finishes.",
      },
    });

    expect(await view.findByText("Your saved comparison is still available.")).toBeInTheDocument();
    expect(view.getByText("Adding another batch")).toBeInTheDocument();
    expect(view.getByText(/New questions unlock when this operation finishes/)).toBeInTheDocument();
    expect(view.queryByLabelText("Message the analyst")).not.toBeInTheDocument();
  });

  it("exposes exact source comparison and adoption for an accepted combined variant", async () => {
    const proposal = {
      kind: "idea_synthesis" as const,
      operation: "combine" as const,
      proposedTitle: "Agency signal desk",
      proposedBrief: "Combines change alerts with a client-ready briefing.",
      changeSummary: "Joins two workflows for the same agency buyer.",
      rationale: "The sources solve adjacent parts of one recurring job.",
      parents: [
        {
          ideaId: "idea-1",
          ideaRevision: 2,
          solutionName: "Change monitor",
          contribution: "Keep the alerting mechanism.",
        },
        {
          ideaId: "idea-2",
          ideaRevision: 4,
          solutionName: "Briefing desk",
          contribution: "Keep the client-ready summary.",
        },
      ],
      evidence: {
        sourceAnchors: [
          { ideaId: "idea-1", ideaRevision: 2, candidateSnapshotSha256: "a".repeat(64) },
          { ideaId: "idea-2", ideaRevision: 4, candidateSnapshotSha256: "b".repeat(64) },
        ],
        requiresValidation: ["Validate that one buyer needs both capabilities."],
      },
      newAssumptions: ["Agencies own both workflows."],
    };
    const receipt = {
      solution_name: "Agency signal desk",
      short_description: "One evaluated agency workflow.",
      market_fit_score: 0.62,
      idea_id: "idea-child",
      idea_revision: 1,
      synthesis_operation: "combine" as const,
      synthesized_from: [
        { idea_id: "idea-1", idea_revision: 2 },
        { idea_id: "idea-2", idea_revision: 4 },
      ],
      synthesis_source_message_id: "asst-combine-accepted",
    };
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [
        {
          id: "asst-combine-accepted",
          gateStage: 5,
          role: "assistant" as const,
          content: "Here is the evaluated combination.",
          patchJson: proposal,
          suggestionsJson: null,
          truncated: false,
          createdAt: "2026-07-16T00:00:00.000Z",
        },
        {
          id: "receipt-combine-accepted",
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
            sourceMessageId: "asst-combine-accepted",
            idea: receipt,
          },
          truncated: false,
          createdAt: "2026-07-16T00:05:00.000Z",
        },
      ],
      weakPool: false,
    } as never);
    const onReviewVariant = vi.fn().mockReturnValue({ ok: true });
    const onUseVariant = vi.fn().mockReturnValue({
      ok: true,
      message: "Replaced 2 source candidates with the combined variant.",
    });
    const onCollapse = vi.fn();

    const view = render(ChatThread, {
      props: {
        jobId: "job-combine-accepted",
        dock: "rail",
        onReviewVariant,
        onUseVariant,
        onCollapse,
      },
    });

    await fireEvent.click(await view.findByRole("button", { name: "Compare with sources" }));
    expect(onReviewVariant).toHaveBeenCalledWith(
      proposal,
      receipt,
      "asst-combine-accepted",
    );
    expect(onCollapse).toHaveBeenCalledOnce();

    await fireEvent.click(view.getByRole("button", { name: "Use variant in shortlist" }));
    expect(onUseVariant).toHaveBeenCalledWith(proposal, receipt, "asst-combine-accepted");
    expect(await view.findByText("Replaced 2 source candidates with the combined variant.")).toBeInTheDocument();
  });
});

describe("ChatThread — chips prefill the composer, drafts persist (never auto-send)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chatLedger.reset();
    vi.mocked(getChatHistory).mockResolvedValue({ messages: [], weakPool: false });
  });

  afterEach(() => {
    cleanup();
  });

  it("starter chip fills and focuses the composer without spending a turn", async () => {
    const { findByText, getByLabelText } = render(ChatThread, {
      props: { jobId: "job-1", dock: "rail", starters: ["Which is easiest to build?"] },
    });

    const chip = await findByText("Which is easiest to build?");
    await fireEvent.click(chip.closest("button")!);

    const textarea = getByLabelText("Message the analyst") as HTMLTextAreaElement;
    await waitFor(() => expect(textarea.value).toBe("Which is easiest to build?"));
    await waitFor(() => expect(document.activeElement).toBe(textarea));
    // Prefill, not send: a send would spend one of the run's limited turns.
    expect(streamChat).not.toHaveBeenCalled();
  });

  it("analyst follow-up chips prefill too", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [
        {
          id: "m1",
          gateStage: 5,
          role: "assistant",
          content: "Rankings are close between the top two.",
          patchJson: null,
          suggestionsJson: ["What separates the top two?"],
          truncated: false,
          createdAt: "1",
        },
      ],
      weakPool: false,
    } as never);

    const { findByText, getByLabelText } = render(ChatThread, {
      props: { jobId: "job-1", dock: "rail" },
    });

    const chip = await findByText("What separates the top two?");
    await fireEvent.click(chip.closest("button")!);

    const textarea = getByLabelText("Message the analyst") as HTMLTextAreaElement;
    await waitFor(() => expect(textarea.value).toBe("What separates the top two?"));
    expect(streamChat).not.toHaveBeenCalled();
  });

  it("seeds the composer from initialDraft and mirrors edits to onDraftChange", async () => {
    const onDraftChange = vi.fn();
    const { getByLabelText } = render(ChatThread, {
      props: {
        jobId: "job-1",
        dock: "rail",
        initialDraft: "half a thought",
        onDraftChange,
      },
    });

    const textarea = getByLabelText("Message the analyst") as HTMLTextAreaElement;
    expect(textarea.value).toBe("half a thought");
    // The mount itself reports the restored draft…
    await waitFor(() => expect(onDraftChange).toHaveBeenCalledWith("half a thought"));

    // …and every edit after it, so close → reopen restores the exact text.
    await fireEvent.input(textarea, { target: { value: "half a thought, finished" } });
    await waitFor(() =>
      expect(onDraftChange).toHaveBeenLastCalledWith("half a thought, finished"),
    );
  });
});

// ── One analyst, one set of rules (audit D15 / D16 / D10) ─────────────────────
//
// The analyst has three entry points — the ranked-ideas workbench, the decision-tool
// routes, and the completed report — reached through EIGHT `ChatThread` mounts
// (selection `+layout.svelte`, `SelectionWorkbench`, `CompletedAnalyst`,
// `GateWorkbench`, and four `SegmentedLedger` slots). An earlier note here said
// "three entry points" as though that were the mount count; it is not, and the
// (mount x card x handler) matrix below has to hold for every one of the eight.
// They used to disagree about three things:
//
//   D16  Entitlement. Only the report page consulted the grant, so on the other two a
//        user without it was handed a composer, wrote a message, spent the send, and
//        met a 402. Entitlement rides on `page.data.featureAccess`, which every (app)
//        navigation already loads, so the surface can say so before the first keystroke.
//
//   D15  Action wiring. The proposal cards are persisted ledger rows and render on
//        EVERY entry point, but only the workbench passes the handlers that carry them
//        out. Elsewhere the same button was enabled and swallowed the click, or sat
//        disabled under "Price hasn't loaded yet" for a price that never arrives.
//
//   D10  Destinations. A result link or a named next step must go to the screen that
//        owns it. Bare fragments (`#solution-selector`, `#examined-ruled-out`) resolve
//        only inside the hub components; from the /selection/* mount the click closed
//        the panel and navigated nowhere. And `#examined-ruled-out` is not enough even
//        ON the hub — it sits inside the appendix's `hidden` body, so the target has no
//        box and the jump is a no-op. Settled results carry an identity (evaluation /
//        idea), so the link uses the query params the workbench's deep-link effect and
//        the detail overlay consume, with the anchor kept only as the identity-less floor.
//
// These assert the rendered surface, not a helper: the defect was what the user saw.
describe("ChatThread — one analyst across every entry point", () => {
  const withAnalystAccess = (granted: boolean) => {
    (page as unknown as { data: Record<string, unknown> }).data = {
      ...page.data,
      featureAccess: { analyst: granted, decisionTools: true },
      featureAccessUnavailable: false,
    };
  };

  /** The entitlement request failed. Not the same thing as a revoked grant. */
  const withEntitlementUnavailable = () => {
    (page as unknown as { data: Record<string, unknown> }).data = {
      ...page.data,
      featureAccess: { analyst: false, decisionTools: false },
      featureAccessUnavailable: true,
    };
  };

  /** No (app) layout data at all — a shared/visitor mount. Must fail closed. */
  const withoutLayoutData = () => {
    const data = { ...page.data } as Record<string, unknown>;
    delete data.featureAccess;
    delete data.featureAccessUnavailable;
    (page as unknown as { data: Record<string, unknown> }).data = data;
  };

  beforeEach(() => {
    vi.clearAllMocks();
    chatLedger.reset();
    vi.mocked(getChatHistory).mockResolvedValue({ messages: [], weakPool: false } as never);
    withAnalystAccess(true);
  });

  afterEach(() => {
    cleanup();
    withAnalystAccess(true);
  });

  it("D16: withholds the composer and says why when the analyst grant is absent", async () => {
    withAnalystAccess(false);

    const view = render(ChatThread, { props: { jobId: "job-1", dock: "rail" } });

    expect(await view.findByText(flatText(ANALYST_LOCKED_NOTICE))).toBeInTheDocument();
    // Nothing to type into — the refusal arrives before the message is composed,
    // not as a 402 after it was sent.
    expect(view.queryByLabelText("Message the analyst")).not.toBeInTheDocument();
    expect(streamChat).not.toHaveBeenCalled();
  });

  it("D16: offers the composer as soon as the grant is present", async () => {
    const view = render(ChatThread, { props: { jobId: "job-1", dock: "rail" } });

    const textarea = (await view.findByLabelText("Message the analyst")) as HTMLTextAreaElement;
    await waitFor(() => expect(textarea.disabled).toBe(false));
    expect(view.queryByText(flatText(ANALYST_LOCKED_NOTICE))).not.toBeInTheDocument();
  });

  it("D15: calls itself the same thing in both docks", async () => {
    const rail = render(ChatThread, { props: { jobId: "job-1", dock: "rail" } });
    expect(await rail.findByText(ANALYST_PANEL_TITLE)).toBeInTheDocument();
    cleanup();
    chatLedger.reset();

    const main = render(ChatThread, { props: { jobId: "job-1", dock: "main" } });
    expect(await main.findByText(ANALYST_PANEL_TITLE)).toBeInTheDocument();
    expect(main.queryByText("Conversation")).not.toBeInTheDocument();
  });

  it("D15: an idea-focus proposal cannot be applied from a host that has no apply handler", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [{
        id: "asst-focus-unwired",
        gateStage: 5,
        role: "assistant",
        content: "Here is a steer for the next batch.",
        patchJson: {
          idea_focus: "novelty",
          rationale: "The pool is crowded around the same distribution play.",
        },
        suggestionsJson: null,
        truncated: false,
        createdAt: "2026-07-16T00:00:00.000Z",
      }],
      weakPool: false,
    } as never);

    const view = render(ChatThread, { props: { jobId: "job-1", dock: "rail" } });

    const apply = (await view.findByText("Apply changes")).closest("button") as HTMLButtonElement;
    expect(apply.disabled).toBe(true);
    expect(view.getByText(flatText(ANALYST_ACTION_NOT_HERE))).toBeInTheDocument();
  });

  it("D15: an unwired seed card names the screen that owns it instead of promising a price", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [seedMessage("asst-seed-unwired")],
      weakPool: false,
    } as never);

    const view = render(ChatThread, { props: { jobId: "job-1", dock: "rail" } });

    const evaluate = (await view.findByText("Evaluate my idea")).closest("button") as HTMLButtonElement;
    expect(evaluate.disabled).toBe(true);
    expect(view.getByText(flatText(ANALYST_ACTION_NOT_HERE))).toBeInTheDocument();
    expect(view.queryByText("Price hasn't loaded yet. Try again in a moment.")).not.toBeInTheDocument();
  });

  it("D15: an unwired copilot card explains its disabled action", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [{
        id: "copilot-unwired",
        gateStage: 5,
        role: "assistant",
        content: "I prepared a draft for review.",
        patchJson: {
          kind: "selection_copilot_action",
          action: "prefill",
          target: "decision_profile",
          ideas: [],
          values: { weeklyTime: "HOURS_10_20" },
          rationale: "Your stated availability should be reviewed in the decision context.",
          caveats: [],
        },
        suggestionsJson: null,
        truncated: false,
        createdAt: "2026-07-16T00:00:00.000Z",
      }],
      weakPool: false,
    } as never);

    const view = render(ChatThread, { props: { jobId: "job-1", dock: "rail" } });

    const review = (await view.findByRole("button", { name: "Review draft" })) as HTMLButtonElement;
    expect(review.disabled).toBe(true);
    expect(view.getByText(flatText(ANALYST_ACTION_NOT_HERE))).toBeInTheDocument();
  });

  // The other half of the matrix. Three cards were asserted for the UNWIRED host;
  // the wired host was only covered incidentally (copilot) or by omission (seed),
  // so nothing guarded against the note appearing next to a live button.
  it("D15: a WIRED host applies an idea-focus proposal and never names another screen", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [{
        id: "asst-focus-wired",
        gateStage: 5,
        role: "assistant",
        content: "Here is a steer for the next batch.",
        patchJson: {
          idea_focus: "novelty",
          rationale: "The pool is crowded around the same distribution play.",
        },
        suggestionsJson: null,
        truncated: false,
        createdAt: "2026-07-16T00:00:00.000Z",
      }],
      weakPool: false,
    } as never);
    const onApplyPatch = vi.fn();

    const view = render(ChatThread, { props: { jobId: "job-1", dock: "rail", onApplyPatch } });

    const apply = (await view.findByText("Apply changes")).closest("button") as HTMLButtonElement;
    expect(apply.disabled).toBe(false);
    expect(view.queryByText(flatText(ANALYST_ACTION_NOT_HERE))).not.toBeInTheDocument();
    await fireEvent.click(apply);
    expect(onApplyPatch).toHaveBeenCalledWith("novelty");
  });

  it("D10: the unwired card's named destination is a real link to ranked ideas", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [seedMessage("asst-seed-note-link")],
      weakPool: false,
    } as never);

    const view = render(ChatThread, { props: { jobId: "job-42", dock: "rail" } });

    // The instruction and the link are the same act: "Open ranked ideas" navigates.
    const link = await view.findByRole("link", { name: ANALYST_ACTION_NOT_HERE_LINK });
    expect(link).toHaveAttribute("href", rankedIdeasHref("job-42"));
    expect(view.getByText(flatText(ANALYST_ACTION_NOT_HERE))).toBeInTheDocument();
  });

  // `#examined-ruled-out` is mounted by RuledOutList INSIDE the appendix body,
  // which ships `hidden` (display:none) until the reader expands it. A target with
  // no box makes fragment navigation a no-op, so the fragment alone drops the
  // reader at the top of the hub with the list still shut. `?evaluationId=` is the
  // actual mechanism: SelectionWorkbench's deep-link $effect consumes it and opens
  // the ruled-out record — the same idiom EvaluationActivity already ships.
  // THE PRODUCTION PATH. A plain user seed is stamped by `withIdentity`
  // (ideaIdentity.ts:39-45), which adds `idea_id`/`idea_revision` and NOTHING else —
  // the result summary carries no `evaluation_id` and the builder never emits a
  // `dispatch_id` on it. Reading the id off the result therefore found nothing and
  // every demoted "Evaluate my idea" card fell to the dead bare fragment. The id
  // lives on the ENVELOPE (`evaluationId`), which chatLedger already reduces to
  // `SeedActivity.evaluationId`.
  it("D10: a demoted PLAIN SEED result deep-links the envelope's evaluation id", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [
        seedMessage("asst-seed-demoted-link"),
        seedSettledReceipt(
          "asst-seed-demoted-link",
          "demoted",
          // Exactly what `withIdentity` stamps — no evaluation_id, no dispatch_id.
          { solution_name: "Invoice reconciler", idea_id: "idea_9f3c", idea_revision: 1 },
          "cmdispatch77",
        ),
      ],
      weakPool: false,
    } as never);

    const view = render(ChatThread, { props: { jobId: "job-42", dock: "rail" } });

    const link = await view.findByRole("link", { name: /view why it was ruled out/i });
    expect(link).toHaveAttribute(
      "href",
      "/jobs/job-42?evaluationId=cmdispatch77#examined-ruled-out",
    );
  });

  // Exact synthesis is the ONE flow that stamps `evaluation_id` onto the result
  // (`stampSynthesizedIdeaIdentity`, ideaIdentity.ts:108-121). Its operationKey IS the
  // dispatch id (workers.ts:2283-2292), so a genuine receipt carries the same value in
  // both places — this pins that the synthesis link did not regress.
  it("D10: a demoted EXACT SYNTHESIS result deep-links its stamped evaluation id", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [
        synthesisMessage("asst-synth-demoted-link"),
        seedSettledReceipt(
          "asst-synth-demoted-link",
          "demoted",
          {
            solution_name: "Agency signal desk",
            idea_id: "idea_7b21",
            idea_revision: 1,
            evaluation_id: "cmdispatch9",
            synthesis_operation: "combine",
          },
          "cmdispatch9",
        ),
      ],
      weakPool: false,
    } as never);

    const view = render(ChatThread, { props: { jobId: "job-42", dock: "rail" } });

    const link = await view.findByRole("link", { name: /view why it was ruled out/i });
    expect(link).toHaveAttribute(
      "href",
      "/jobs/job-42?evaluationId=cmdispatch9#examined-ruled-out",
    );
  });

  // A LEGACY row, written before the envelope carried `evaluationId`: the only identity
  // left is the synthesis stamp on the result. chatLedger's compat chain
  // (`...?? idea.evaluation_id ?? idea.dispatch_id`, chatLedger.svelte.ts:256-259) still
  // resolves it, so history keeps its deep link instead of degrading to the fragment.
  // The "legacy op 4" value is a URL-ENCODING probe, not a historical row — a real
  // legacy synthesis operationKey was `dispatch.sourceMessageId`, a cuid with no spaces.
  // It is here to pin that whatever identity the chain resolves is encoded into the href.
  it("D10: a legacy receipt with no envelope id still deep-links via the stamped result", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [
        synthesisMessage("asst-synth-demoted-legacy"),
        seedSettledReceipt("asst-synth-demoted-legacy", "demoted", {
          solution_name: "Agency signal desk",
          idea_id: "idea_7b21",
          idea_revision: 1,
          evaluation_id: "legacy op 4",
        }),
      ],
      weakPool: false,
    } as never);

    const view = render(ChatThread, { props: { jobId: "job-42", dock: "rail" } });

    const link = await view.findByRole("link", { name: /view why it was ruled out/i });
    expect(link).toHaveAttribute(
      "href",
      "/jobs/job-42?evaluationId=legacy%20op%204#examined-ruled-out",
    );
  });

  // A receipt with no operation identity still has to land SOMEWHERE real, so the
  // bare fragment stays as the floor — never a dead `#` or a link to nothing.
  it("D10: a demoted result with no evaluation identity falls back to the hub fragment", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [
        seedMessage("asst-seed-demoted-bare"),
        seedSettledReceipt("asst-seed-demoted-bare", "demoted"),
      ],
      weakPool: false,
    } as never);

    const view = render(ChatThread, { props: { jobId: "job-42", dock: "rail" } });

    const link = await view.findByRole("link", { name: /view why it was ruled out/i });
    expect(link).toHaveAttribute("href", "/jobs/job-42#examined-ruled-out");
  });

  // "View full candidate details" pointed at the FIRST ranked row, so the link and
  // its label disagreed for every result but the top one.
  it("D10: an accepted seed result links to its own candidate, not the first ranked row", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [
        seedMessage("asst-seed-accepted-link"),
        seedSettledReceipt("asst-seed-accepted-link", "accepted", {
          solution_name: "Invoice reconciler",
          idea_id: "idea a7",
          idea_revision: 3,
        }),
      ],
      weakPool: false,
    } as never);

    const view = render(ChatThread, { props: { jobId: "job-42", dock: "rail" } });

    const link = await view.findByRole("link", { name: /view full candidate details/i });
    expect(link).toHaveAttribute(
      "href",
      "/jobs/job-42?detailTab=overview&ideaId=idea%20a7&ideaRevision=3",
    );
  });

  it("D10: an accepted synthesis result defaults the revision and falls back to ranked ideas", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [
        synthesisMessage("asst-synth-accepted-link"),
        seedSettledReceipt("asst-synth-accepted-link", "accepted", {
          solution_name: "Agency signal desk",
          idea_id: "idea-b2",
        }),
        synthesisMessage("asst-synth-accepted-bare"),
        seedSettledReceipt("asst-synth-accepted-bare", "accepted", {
          solution_name: "Agency signal desk II",
        }),
      ],
      weakPool: false,
    } as never);

    const view = render(ChatThread, { props: { jobId: "job-42", dock: "rail" } });

    const links = await view.findAllByRole("link", { name: /view evaluated candidate/i });
    expect(links[0]).toHaveAttribute(
      "href",
      "/jobs/job-42?detailTab=overview&ideaId=idea-b2&ideaRevision=1",
    );
    expect(links[1]).toHaveAttribute("href", rankedIdeasHref("job-42"));
  });

  it("D16: the locked notice links to billing instead of naming an action with no route", async () => {
    withAnalystAccess(false);

    const view = render(ChatThread, { props: { jobId: "job-1", dock: "rail" } });

    expect(await view.findByText(flatText(ANALYST_LOCKED_NOTICE))).toBeInTheDocument();
    expect(view.getByRole("link", { name: ANALYST_LOCKED_LINK }))
      .toHaveAttribute("href", ANALYST_BILLING_HREF);
  });

  it("D16: an unreadable entitlement keeps the composer and never claims the user is unsubscribed", async () => {
    withEntitlementUnavailable();

    const view = render(ChatThread, { props: { jobId: "job-1", dock: "rail" } });

    // A transient fetch failure must not tell a paying subscriber to subscribe.
    expect(await view.findByText(ANALYST_ENTITLEMENT_UNAVAILABLE_NOTICE)).toBeInTheDocument();
    expect(view.queryByText(flatText(ANALYST_LOCKED_NOTICE))).not.toBeInTheDocument();
    const textarea = (await view.findByLabelText("Message the analyst")) as HTMLTextAreaElement;
    await waitFor(() => expect(textarea.disabled).toBe(false));
  });

  it("D16: still fails closed when there is no layout data at all", async () => {
    withoutLayoutData();

    const view = render(ChatThread, { props: { jobId: "job-1", dock: "rail" } });

    expect(await view.findByText(flatText(ANALYST_LOCKED_NOTICE))).toBeInTheDocument();
    expect(view.queryByText(ANALYST_ENTITLEMENT_UNAVAILABLE_NOTICE)).not.toBeInTheDocument();
    expect(view.queryByLabelText("Message the analyst")).not.toBeInTheDocument();
  });
});
