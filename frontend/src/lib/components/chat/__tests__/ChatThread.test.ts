import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, fireEvent, cleanup, waitFor } from "@testing-library/svelte";
import ChatThread from "../ChatThread.svelte";
import { streamChat, getChatHistory, ApiError } from "$lib/api";
import type { ChatStreamEvent } from "$lib/api";
import { chatLedger } from "$lib/stores/chatLedger.svelte";

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

    const { findByText } = render(ChatThread, { props: { jobId: "job-1", dock: "rail", seedCost: null } });

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
    expect(getByRole("link", { name: /view full candidate details/i })).toHaveAttribute("href", "#solution-selector");
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
