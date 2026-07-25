<script lang="ts">
  // Guided-chat thread — Phase A (plans/eager-meandering-feather.md). ONE component
  // for both docks: `rail` (wired here, beside SelectionWorkbench at G3/
  // AWAITING_SELECTION, chatMode-independent — every entitled user gets it) and
  // `main` (Phase B, G1/G2 gate thread — unwired until then).
  //
  // Visual direction (revised 2026-07-12): a CONVERSATION, in the house voice.
  // The old treatment made every turn an identical full-width row with a hairline
  // under it — a table of speech. Speakers now differ in kind: your question is a
  // compact card addressed to the analyst; the analyst's answer is open prose that
  // owns the column, with real markdown typography (lists, emphasis, code — the
  // renderer emits them and the app's reset was flattening them). Still no avatars,
  // no typing dots, no chat-app kitsch; the composer is one field with the send
  // control inside it, and orange stays on the send action alone.
  import { tick } from "svelte";
  import { ArrowRight, ArrowDown, Check, Coins, Loader2, Maximize2, Minimize2, Search, Wand2, X } from "lucide-svelte";
  import Composer from "./Composer.svelte";
  import IdeaReferenceText from "$lib/components/IdeaReferenceText.svelte";
  import {
    streamChat,
    ApiError,
    isGatePatch,
    isLedgerEvent,
    isIdeaSynthesisPatch,
    isNewIdeaSeedPatch,
    isSelectionCopilotAction,
    isIdeaFocusPatch,
    type ChatPatch,
    type IdeaSynthesisPatch,
    type SynthesisIntent,
    type SelectionWorkspaceContext,
    type NewIdeaSeedPatch,
    type SeedResultSummary,
    type SelectionCopilotAction,
    type GateG1PatchFields,
    type GateG2PatchFields,
    type GateArtifact,
  } from "$lib/api";
  import type { IdeaFocus } from "$lib/api";
  import type { IdeaReference } from "$lib/utils/ideaReferences";
  import { GATE_FIELD_LABEL, formatGateFieldValue } from "$lib/components/gate/gateFields";
  import { chatLedger, type LedgerMessage } from "$lib/stores/chatLedger.svelte";

  interface Props {
    jobId: string;
    dock: "main" | "rail";
    /** Gate this thread is anchored to. Rail dock (G3) only ever uses 5 (sentinel);
     *  main dock (G1/G2) passes 1 or 4. */
    gateStage?: number;
    /** Current regen focus at the call site (SelectionWorkbench), so the G3 patch
     *  card's before→after diff reflects reality instead of assuming "Balanced". */
    currentIdeaFocus?: IdeaFocus;
    /** G1/G2 only — the gate's current artifact, used to resolve "before" values
     *  for the patch diff card. */
    gateArtifact?: GateArtifact | null;
    /** True while the parent is mid-regenerate (G3) or mid-apply (G1/G2) —
     *  disables Apply so a second patch can't land on top of an in-flight one. */
    applying?: boolean;
    /** G1/G2 only — apply_stay cap (5/gate) reached; disables Apply with a note
     *  instead of firing a request that will 400. */
    applyCapReached?: boolean;
    /** G3 (AWAITING_SELECTION) — parent owns the actual regenerate call (it
     *  already has the credit/402 handling); this just hands back the approved steer. */
    onApplyPatch?: (ideaFocus: IdeaFocus) => void | Promise<void>;
    /** G1/G2 (AWAITING_GATE) — parent owns the gate-action apply_stay call; this
     *  hands back the whitelisted patch fields the user approved, plus the id of
     *  the proposing message so the parent can mark it applied on round-trip. */
    onApplyGatePatch?: (patch: GateG1PatchFields | GateG2PatchFields, messageId?: string) => void | Promise<void>;
    /** G1/G2 only — ids of patch messages whose apply round-trip completed; their
     *  proposal cards render a terminal "Applied" state instead of live actions. */
    appliedPatchIds?: ReadonlySet<string>;
    /** G3 (rail dock) only — the `seed_idea` flat stage cost (billing/stage-costs),
     *  shown on a `new_idea_seed` patch card. Null/undefined → price hasn't loaded
     *  (or the deployment predates it); Evaluate stays disabled with an explanation
     *  rather than firing a request with no agreed-upon price. */
    seedCost?: number | null;
    /** G3 (rail dock) only — parent owns the seedIdea() call (credit/402/409 CAS
     *  handling, optimistic pending mark via chatLedger.markSeedPending), exactly
     *  like onApplyPatch owns regenerate; this just hands back the approved seed
     *  and the id of the proposing message (the card's durable identity). */
    onSeedSubmit?: (patch: NewIdeaSeedPatch | IdeaSynthesisPatch, messageId: string) => void | Promise<void>;
    /** Accepted synthesis only. The parent revalidates operation, source message,
     *  child revision, and every source revision before allowing either action. */
    onReviewVariant?: (patch: IdeaSynthesisPatch, receipt: SeedResultSummary, messageId: string) => { ok: boolean; message?: string };
    onUseVariant?: (patch: IdeaSynthesisPatch, receipt: SeedResultSummary, messageId: string) => { ok: boolean; message?: string };
    /** Selection-stage copilot cards only prepare navigation or owner-reviewed drafts.
     *  The parent validates canonical identity/version and owns every destination. */
    onCopilotAction?: (
      action: SelectionCopilotAction,
      messageId: string,
    ) => { ok: boolean; message?: string } | Promise<{ ok: boolean; message?: string }>;
    /** True while the parent is mid-mutation (regenerate/apply_stay/continue) —
     *  locks every way to submit a turn (composer, Enter, starter/follow-up chips)
     *  so a chat turn can't race a checkpoint transition into a 409. */
    blocked?: boolean;
    /** Live job state shown in place of the composer while `blocked`. The parent
     * owns these labels because it has the worker/SSE fields; ChatThread only
     * owns the persistent analyst surface. */
    blockedTitle?: string;
    blockedDetail?: string;
    /** Starter questions derived from state by the caller. Used only before the user
     *  starts this conversation; once a turn exists, only analyst-authored follow-ups
     *  can render. This prevents a failed suggestion call from snapping back to an
     *  unrelated screen-level topic. Clicking one PREFILLS the composer and focuses
     *  it — never auto-sends, because each send spends one of the run's limited
     *  turns; the user reviews/edits and presses Enter themselves. Follow-up chips
     *  behave the same way. */
    starters?: string[];
    /** Starter-chip plumbing for callers that trigger a prompt from OUTSIDE the panel
     *  — when set to a non-null string it PREFILLS the composer and moves focus there
     *  (never auto-sends: each send spends one of the run's limited questions, so the
     *  user reviews/edits and presses Enter themselves); `onStarterConsumed` fires
     *  once consumed so the caller can reset it (re-arms repeat clicks). */
    starterPrompt?: string | null;
    /** Exact owner-selected synthesis sources paired with `starterPrompt`. */
    starterSynthesisIntent?: SynthesisIntent | null;
    /** Current selection workspace and exact revisions. The backend resolves
     *  these against the owner job before adding them to the analyst prompt. */
    selectionContext?: SelectionWorkspaceContext | null;
    onStarterConsumed?: () => void;
    /** Archived-segment rendering (SegmentedLedger past checkpoints / completed
     *  transcript): no head, no composer, patch cards terminal-only, receipts
     *  muted, no entrance animations. The conversation is history, not a surface. */
    readOnly?: boolean;
    /** Whether THIS thread owns the "couldn't load the conversation" retry. False when the host
     *  already renders one (SegmentedLedger does), so a single failed fetch doesn't paint the same
     *  Retry button once per mounted thread. */
    showHistoryRetry?: boolean;
    /** Panel controls, rendered in the head when the host is a dockable panel
     *  (selection rail / focus overlay). Absent → no chrome, as on the gate card. */
    onCollapse?: () => void;
    onToggleFocus?: () => void;
    focused?: boolean;
    /** G3 (rail dock) only — set from the chat-history response's `weakPool` flag
     *  (free-culture wallet, no idea cleared a strong market-fit bar). Bindable so
     *  SelectionWorkbench can render the "Should I even proceed with this niche?"
     *  starter chip without a second history fetch. */
    weakPool?: boolean;
    /** Current report ideas that assistant prose may mention. Optional because
     *  archived and gate-level threads do not own an idea-details surface. */
    ideaReferences?: readonly IdeaReference[];
    onOpenIdeaReference?: (reference: IdeaReference) => void;
    /** Draft persistence for hosts that unmount this thread on close (the
     *  selection overlay): `initialDraft` seeds the composer on mount, and
     *  `onDraftChange` mirrors every edit back so an Esc/scrim-click close
     *  never destroys what the user was writing. */
    initialDraft?: string;
    onDraftChange?: (text: string) => void;
  }

  let {
    jobId,
    dock,
    gateStage = 5,
    currentIdeaFocus = "auto",
    gateArtifact = null,
    applying = false,
    applyCapReached = false,
    onApplyPatch,
    onApplyGatePatch,
    appliedPatchIds = new Set<string>(),
    seedCost = null,
    onSeedSubmit,
    onReviewVariant,
    onUseVariant,
    onCopilotAction,
    blocked = false,
    blockedTitle = "Research is active",
    blockedDetail = "The analyst will unlock at the next checkpoint.",
    starters = [],
    starterPrompt = null,
    starterSynthesisIntent = null,
    selectionContext = null,
    onStarterConsumed,
    weakPool = $bindable(false),
    ideaReferences = [],
    onOpenIdeaReference,
    initialDraft = "",
    onDraftChange,
    readOnly = false,
    showHistoryRetry = true,
    onCollapse,
    onToggleFocus,
    focused = false,
  }: Props = $props();

  // Ledger rows come from the shared per-job store (chatLedger) so every surface
  // — checkpoint page, selection rail, run shell, completed transcript — reads
  // one cached thread and remounts flash-free. This component renders ONE gate
  // stage's conversational slice and owns the composer/streaming for it.
  type ThreadMessage = LedgerMessage;

  const FOCUS_LABEL: Record<IdeaFocus, string> = {
    auto: "Balanced",
    novelty: "Differentiation",
    distribution: "Distribution",
  };

  const SYNTHESIS_LABEL: Record<IdeaSynthesisPatch["operation"], string> = {
    narrow: "Narrow",
    reposition: "Reposition",
    combine: "Combine",
    adjacent: "Explore adjacent",
  };

  /** "Before" value for a G1/G2 patch field, read from the gate's current artifact. */
  function gateFieldBefore(field: string, artifact: GateArtifact | null | undefined): string {
    if (!artifact) return "(unknown)";
    const a = artifact as Record<string, unknown>;
    switch (field) {
      case "niche_description":
        return formatGateFieldValue(field, a.niche_description);
      case "market_segments":
        return formatGateFieldValue(field, a.market_segments);
      case "industry_boundaries":
        return formatGateFieldValue(field, a.industry_boundaries);
      case "primary_target_segment":
        return formatGateFieldValue(field, a.primary_target);
      case "user_target_audience":
      case "excluded_segments":
      case "segment_emphasis":
      case "pain_scope":
        // Not tracked on the artifact itself (no exclusions/emphasis/scope exist
        // until a patch sets them) — the diff reads as an addition, not a change.
        return "(not set)";
      default:
        return "(unknown)";
    }
  }

  /** Exhaustiveness guard — a fifth ChatPatch variant that reaches here without a
   *  matching branch is a compile error at the call site, not a silent fallthrough.
   *  (Previously an unrecognized patch quietly rendered as an idea-focus proposal —
   *  the bug this whole dispatch was rewritten to close.) */
  function assertNever(x: never): never {
    throw new Error(`Unhandled ChatPatch: ${JSON.stringify(x)}`);
  }

  /** The before→after rows a proposal card shows. Built here rather than inline so
   *  the gate-vs-idea-focus narrowing happens in TypeScript, not in template consts
   *  (where the union doesn't narrow across `{@const}` boundaries). */
  function proposalRows(patch: ChatPatch): { label: string; before: string; after: string }[] {
    if (isGatePatch(patch)) {
      return Object.entries(patch.patch).map(([field, value]) => ({
        label: GATE_FIELD_LABEL[field] ?? field,
        before: gateFieldBefore(field, gateArtifact),
        after: formatGateFieldValue(field, value),
      }));
    }
    if (isLedgerEvent(patch)) return [];
    // Rendered by dedicated cards below, never the generic diff table.
    if (isNewIdeaSeedPatch(patch) || isIdeaSynthesisPatch(patch) || isSelectionCopilotAction(patch)) return [];
    if (isIdeaFocusPatch(patch)) {
      return [
        {
          label: "Idea focus",
          before: FOCUS_LABEL[currentIdeaFocus],
          after: FOCUS_LABEL[patch.idea_focus],
        },
      ];
    }
    return assertNever(patch);
  }

  const messages = $derived(
    chatLedger
      .segmentMessages(gateStage)
      .filter((m) => m.role === "user" || m.role === "assistant" || m.role === "receipt"),
  );
  const historyLoaded = $derived(chatLedger.historyLoaded);
  const loadFailed = $derived(chatLedger.loadFailed);
  let locked = $state(false); // 402 on send — not entitled
  // Seeded from the host-persisted draft ONCE at mount (the host remounts this
  // component per open, so a live two-way sync would be circular for no gain).
  // svelte-ignore state_referenced_locally
  let input = $state(initialDraft);
  let sending = $state(false);
  let hasStreamStarted = $state(false);
  let streamingContent = $state("");
  /** Read-only tool receipts for the IN-FLIGHT turn (chat agent tools v1.1) — labels
   *  arrive live via SSE `tool` events, always before any streamed answer tokens; cleared
   *  once the turn's `done`/error lands (the persisted message then carries its own
   *  `toolCallsJson` for reloads). */
  let pendingToolLabels = $state<string[]>([]);
  let sendError = $state("");
  /** Text of a turn that failed — offered back via a Retry control. */
  let failedDraft = $state("");
  let failedSynthesisIntent = $state<SynthesisIntent | null>(null);
  let pendingSynthesisIntent = $state<SynthesisIntent | null>(null);
  // Backend 'note' SSE event — a neutral mid-stream explanation (e.g. the gate
  // changed while generating, so a proposed patch was dropped). Not an error.
  let sendNote = $state("");
  let variantActionFeedback = $state<Record<string, { failed: boolean; message: string }>>({});
  let copilotActionFeedback = $state<Record<string, { failed: boolean; message: string }>>({});
  let listEl: HTMLDivElement | undefined = $state();
  let composerRef: Composer | undefined = $state();
  let composerFocused = $state(false);
  let abortController: AbortController | null = null;

  // GLOBAL turn usage — the backend cap is 30 per JOB, not per gate; showing a
  // per-gate count silently understated real usage.
  const userTurnCount = $derived(chatLedger.usedTurns);
  const maxTurns = $derived(chatLedger.maxTurns);

  // At the cap the composer stops accepting input, with an explanation. Previously the wall only
  // appeared AFTER you wrote a message and sent it into a 429 — and the client couldn't even tell
  // that 429 apart from a rate limit, so it showed "try again" for a limit no retry can clear.
  const atTurnCap = $derived(userTurnCount >= maxTurns);
  const operationBlocked = $derived(blocked || chatLedger.operationActive);

  $effect(() => {
    void loadHistory();
  });

  // Every edit is mirrored to the host, so a close that unmounts this thread
  // (Esc, scrim click) can hand the exact draft back to the next mount.
  $effect(() => {
    onDraftChange?.(input);
  });

  $effect(() => {
    const prompt = starterPrompt;
    if (!prompt || !historyLoaded || sending || locked || readOnly || atTurnCap || operationBlocked || loadFailed) return;
    // Prefill only — sending spends one of the run's limited questions, so the
    // user reviews/edits the seeded prompt and presses Enter themselves.
    input = prompt;
    pendingSynthesisIntent = starterSynthesisIntent;
    onStarterConsumed?.();
    void tick().then(() => composerRef?.focus());
  });

  async function loadHistory() {
    // Fetch/caching lives in the shared store (idempotent per job); load-failure
    // semantics unchanged — GET history is auth+ownership only, so failures are
    // genuine load errors, never entitlement (that's enforced on send()).
    const historyJobId = jobId;
    await chatLedger.init(historyJobId);
    if (jobId !== historyJobId) return;

    // Existing conversations mount at the latest turn. Wait for the transcript and
    // its follow-ups to render before measuring the scroll height.
    await tick();
    scrollToEnd(true);
  }

  // Retry affordance for a failed history load (same store call + in-flight guard
  // as SegmentedLedger's retry — reused here rather than reinvented).
  let retryingHistory = $state(false);
  async function retryHistory() {
    if (retryingHistory) return;
    retryingHistory = true;
    try {
      await chatLedger.reload();
    } finally {
      retryingHistory = false;
    }
  }

  // weakPool is learned from the history response; keep the bindable in sync so
  // SelectionWorkbench's starter chip keeps working across store reloads.
  $effect(() => {
    weakPool = chatLedger.weakPool;
  });

  // Streaming must never yank a reader away from where they are. Autoscroll only
  // while the user is already at the bottom (i.e. following along); the moment they
  // scroll up to re-read, the stream keeps running but the viewport stays put and a
  // "Jump to latest" control appears.
  const NEAR_BOTTOM_PX = 48;
  let stickToBottom = $state(true);
  function onListScroll() {
    if (!listEl) return;
    stickToBottom = listEl.scrollHeight - listEl.scrollTop - listEl.clientHeight <= NEAR_BOTTOM_PX;
  }
  function scrollToEnd(force = false, behavior?: ScrollBehavior) {
    if (!force && !stickToBottom) return;
    const reduce =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    requestAnimationFrame(() => {
      listEl?.scrollTo?.({
        top: listEl.scrollHeight,
        behavior: behavior ?? (reduce ? "auto" : "smooth"),
      });
    });
  }

  async function alignExpandedThread() {
    // The parent changes this thread's width and height when `focused` flips. Two
    // animation frames let that layout commit before scrollHeight is measured.
    await tick();
    requestAnimationFrame(() => {
      if (!focused) return;
      stickToBottom = true;
      scrollToEnd(true, "auto");
    });
  }

  $effect(() => {
    if (!focused || !historyLoaded) return;
    void alignExpandedThread();
  });

  function jumpToLatest() {
    stickToBottom = true;
    scrollToEnd(true);
  }

  async function send() {
    const text = input.trim();
    if (!text || sending || locked || atTurnCap || operationBlocked || loadFailed) return;
    // Snapshot the job this turn belongs to. `jobId` is a reactive prop — reading it
    // later, inside the async onEvent callbacks below, would pick up whatever job the
    // component has SINCE navigated to (SvelteKit can update this component's props in
    // place across a route change rather than destroying/recreating it). chatLedger is
    // a page-scoped singleton, so a late callback that used the live `jobId` instead of
    // this snapshot would happily append job A's reply into job B's ledger.
    const requestJobId = jobId;
    const synthesisIntent = pendingSynthesisIntent;
    pendingSynthesisIntent = null;
    // Optimistic: clear the composer and show the turn — but remember both, because either kind
    // of failure has to be undone.
    //   - TRANSPORT failure (never reached the server): restore the draft, retract the phantom.
    //   - Server `error` EVENT: the server now DELETES the user row when its generation produced
    //     nothing (a turn the user never got an answer to must not cost them one of their 30), and
    //     tells us so via retractMessageId — so we retract to match.
    // On success the id is replaced by the persisted one from the `done` event.
    const optimisticId = `local-${Date.now()}`;
    input = "";
    sendError = "";
    sendNote = "";
    failedDraft = "";
    failedSynthesisIntent = null;
    chatLedger.appendLocal(requestJobId, { id: optimisticId, gateStage, role: "user", content: text });
    sending = true;
    hasStreamStarted = false;
    streamingContent = "";
    pendingToolLabels = [];
    // Sending is an explicit act — always land on your own message.
    jumpToLatest();

    abortController = new AbortController();
    try {
      await streamChat(requestJobId, text, {
        signal: abortController.signal,
        synthesisIntent: synthesisIntent ?? undefined,
        selectionContext: selectionContext ?? undefined,
        onEvent: (evt) => {
          if (evt.type === "token") {
            hasStreamStarted = true;
            streamingContent += evt.delta;
            scrollToEnd();
          } else if (evt.type === "tool") {
            pendingToolLabels = [...pendingToolLabels, evt.label];
            scrollToEnd();
          } else if (evt.type === "done") {
            // Give the optimistic user row its real id BEFORE anything can reload history.
            // Reconciliation keeps every `local-` row the server doesn't know about, so leaving
            // the temporary id in place makes the next reload render the question twice.
            if (evt.userMessageId) {
              chatLedger.promoteUserMessage(requestJobId, optimisticId, evt.userMessageId);
            }
            chatLedger.setUsedTurns(requestJobId, evt.usedTurns);
            chatLedger.appendLocal(requestJobId, {
              id: evt.message.id,
              gateStage,
              role: "assistant",
              content: evt.message.content,
              patchJson: evt.message.patchJson ?? null,
              toolCallsJson: evt.message.toolCallsJson ?? null,
              suggestionsJson: evt.message.suggestionsJson ?? null,
            });
            streamingContent = "";
            pendingToolLabels = [];
          } else if (evt.type === "note") {
            sendNote = evt.note;
          } else if (evt.type === "error") {
            sendError = evt.error || "The analyst couldn't respond. Try again.";
            // The server rolled the turn back (its generation produced nothing, so it must not
            // cost the user a turn). Retract our copy to match, or the question is stranded in
            // the thread with no answer under it — and the turn counter disagrees with the server.
            if (evt.retractMessageId) {
              chatLedger.retractLocal(requestJobId, optimisticId);
            }
            chatLedger.setUsedTurns(requestJobId, evt.usedTurns);
            // The turn failed on the server. The user's words are the one thing we
            // must not lose: hand them back so a retry is one keystroke, not a retype.
            failedDraft = text;
            failedSynthesisIntent = synthesisIntent;
          }
        },
      });
    } catch (e) {
      const aborted = e instanceof DOMException && e.name === "AbortError";
      if (aborted) {
        // swallow — stopStreaming() already reflects the user's intent
        // (the turn may still have been persisted server-side, so keep it).
      } else {
        // Transport-level failure: the message never landed. Retract the
        // optimistic turn and hand the draft back so nothing is lost.
        chatLedger.retractLocal(requestJobId, optimisticId);
        if (!input.trim()) input = text;
        failedSynthesisIntent = synthesisIntent;
        if (e instanceof ApiError && e.status === 402) {
          locked = true;
        } else if (e instanceof ApiError && e.status === 409) {
          sendError = "This checkpoint moved on. Your message wasn't sent.";
        } else {
          sendError = e instanceof ApiError ? e.message : "The analyst couldn't respond. Try again.";
        }
      }
    } finally {
      sending = false;
      hasStreamStarted = false;
      streamingContent = "";
      pendingToolLabels = [];
      abortController = null;
      scrollToEnd();
    }
  }

  // BLOCKER fix: an in-flight stream for the OLD job must never survive past a
  // navigation. `jobId` changing (SvelteKit can update this component's props in place
  // across a route change rather than destroying it) or the component unmounting both
  // run this cleanup — either way, stopStreaming() aborts the fetch so no further
  // onEvent callback fires for a job this thread no longer represents. The chatLedger
  // jobId guard (see send() above) is the second, independent layer: even a callback
  // that sneaks in before the abort takes effect is dropped there.
  $effect(() => {
    void jobId;
    return () => {
      stopStreaming();
    };
  });

  /** Exposed to parents via `bind:this` so they can abort an in-flight stream
   *  before firing their own gate/regenerate actions (Phase C wiring). Reuses
   *  the exact same abort path as the Stop button — no-op if nothing is
   *  streaming, since `abortController` is null when idle. */
  export function stopStreaming() {
    abortController?.abort();
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  }

  /** A suggested question is a DRAFT the user didn't have to type — it fills the
   *  composer and moves focus there. Sending still costs one of the run's limited
   *  turns, so the user reviews/edits and presses Enter themselves (same contract
   *  as the external `starterPrompt` plumbing above). */
  function prefillStarter(chip: string) {
    if (sending || locked || atTurnCap || operationBlocked || loadFailed) return;
    input = chip;
    void tick().then(() => composerRef?.focus());
  }

  async function applyPatch(msg: ThreadMessage) {
    // Ledger-event payloads are receipts, not proposals — nothing to apply.
    if (!msg.patchJson || applying || isLedgerEvent(msg.patchJson)) return;
    const patch = msg.patchJson;
    if (isGatePatch(patch)) {
      if (applyCapReached || !onApplyGatePatch) return;
      await onApplyGatePatch(patch.patch, msg.id);
    } else if (isNewIdeaSeedPatch(patch) || isIdeaSynthesisPatch(patch)) {
      if (!onSeedSubmit) return;
      await onSeedSubmit(patch, msg.id);
    } else if (isSelectionCopilotAction(patch)) {
      // Copilot actions are review/navigation receipts. Their dedicated card may
      // only call onCopilotAction; the generic mutation dispatcher never executes them.
      return;
    } else if (isIdeaFocusPatch(patch)) {
      if (!onApplyPatch) return;
      await onApplyPatch(patch.idea_focus);
    } else {
      assertNever(patch);
    }
  }

  function dismissPatch(target: ThreadMessage) {
    chatLedger.dismissPatch(target.id);
  }

  function copilotButtonLabel(action: SelectionCopilotAction): string {
    if (action.action === "shortlist_review") return "Review shortlist";
    if (action.action === "prefill" && action.target === "concept_forge") return "Review directions brief";
    if (action.action === "prefill") return "Review draft";
    if (action.target === "candidate") return "Open candidate";
    return "Open workspace";
  }

  function copilotPrefillSupported(action: SelectionCopilotAction): boolean {
    return action.action !== "prefill"
      || action.target === "decision_profile"
      || action.target === "experiment"
      || action.target === "concept_forge"
      || action.target === "assumption"
      || action.target === "owner_evidence";
  }

  async function handleCopilotAction(action: SelectionCopilotAction, messageId: string) {
    if (!onCopilotAction || applying || operationBlocked || !copilotPrefillSupported(action)) return;
    try {
      const result = await onCopilotAction(action, messageId);
      copilotActionFeedback = {
        ...copilotActionFeedback,
        [messageId]: {
          failed: !result.ok,
          message: result.message ?? (result.ok ? "Opened for your review." : "This suggestion is no longer current."),
        },
      };
      if (result.ok) onCollapse?.();
    } catch (cause) {
      copilotActionFeedback = {
        ...copilotActionFeedback,
        [messageId]: {
          failed: true,
          message: cause instanceof Error ? cause.message : "This suggestion could not be opened.",
        },
      };
    }
  }

  function handleVariantAction(
    action: "review" | "use",
    patch: IdeaSynthesisPatch,
    receipt: SeedResultSummary,
    messageId: string,
  ) {
    const result = action === "review"
      ? onReviewVariant?.(patch, receipt, messageId)
      : onUseVariant?.(patch, receipt, messageId);
    if (!result) return;
    if (action === "review" && result.ok) {
      onCollapse?.();
      return;
    }
    variantActionFeedback = {
      ...variantActionFeedback,
      [messageId]: {
        failed: !result.ok,
        message: result.message
          ?? (result.ok ? "Variant is now in your shortlist." : "Could not update the shortlist."),
      },
    };
  }

  /** Exposed to GateWorkbench: append an applied-change receipt as the newest
   *  ledger entry, so the confirmation lands where the user just acted instead
   *  of only mutating the framing document further up the panel. */
  export function appendReceipt(receipt: { rows: { label: string; value: string }[]; note: string }) {
    chatLedger.appendLocal(jobId, { id: `local-receipt-${Date.now()}`, gateStage, role: "receipt", content: "", receipt });
    jumpToLatest();
  }

  const CONTEXTUAL_FALLBACKS = [
    "Go deeper on this answer",
    "Show the supporting evidence",
    "What should I consider next?",
  ];

  // The analyst's own follow-ups for its latest turn win. Older persisted answers
  // have none, so they receive context-relative prompts rather than disappearing or
  // pivoting back to screen-level ranked-idea starters from a different topic.
  const latestAssistant = $derived([...messages].reverse().find((m) => m.role === "assistant"));
  const analystSuggestions = $derived(latestAssistant?.suggestionsJson ?? null);
  const conversationStarted = $derived(messages.some((m) => m.role === "user"));
  const awaitingProposalDecision = $derived.by(() => {
    const message = latestAssistant;
    if (readOnly || !message?.patchJson || message.dismissed || isLedgerEvent(message.patchJson)) {
      return false;
    }
    if (isNewIdeaSeedPatch(message.patchJson) || isIdeaSynthesisPatch(message.patchJson)) {
      return chatLedger.seedOutcome(message.id) == null;
    }
    return !appliedPatchIds.has(message.id);
  });
  const activeStarters = $derived(
    awaitingProposalDecision
      ? []
      : analystSuggestions?.length
      ? analystSuggestions
      : conversationStarted
        ? CONTEXTUAL_FALLBACKS
        : starters,
  );
</script>

<aside
  class="chat-thread chat-thread--{dock}"
  class:chat-thread--readonly={readOnly}
  class:chat-thread--focus={focused}
  aria-label="Research analyst chat"
>
  {#if !readOnly}
    <header class="chat-head">
      <div class="chat-identity">
        <div class="chat-title-line">
          <span class="chat-title">{dock === "main" ? "Conversation" : "Analyst"}</span>
          <span class="chat-grounding">
            <Search class="chat-grounding-icon" aria-hidden="true" />
            Dossier-backed
          </span>
        </div>
        <span class="chat-subtitle">Answers use evidence from this research run</span>
      </div>
      {#if historyLoaded && !locked && !loadFailed}
        <span
          class="chat-head-count"
          title="Questions this run · {userTurnCount} of {maxTurns} used"
          aria-label="Questions this run · {userTurnCount} of {maxTurns} used"
        >
          <span class="chat-head-count-value">{userTurnCount}</span>
          <span class="chat-head-count-copy">of {maxTurns} <span class="chat-head-count-noun">questions</span></span>
        </span>
      {/if}
      {#if onToggleFocus || onCollapse}
        <div class="chat-head-actions">
          {#if onToggleFocus}
            <button
              type="button"
              class="chat-head-btn"
              onclick={onToggleFocus}
              aria-label={focused ? "Dock the conversation beside the candidates" : "Read the conversation full width"}
              title={focused ? "Dock beside candidates" : "Read full width"}
            >
              {#if focused}
                <Minimize2 class="w-3.5 h-3.5" aria-hidden="true" />
              {:else}
                <Maximize2 class="w-3.5 h-3.5" aria-hidden="true" />
              {/if}
            </button>
          {/if}
          {#if onCollapse}
            <button type="button" class="chat-head-btn" onclick={onCollapse} aria-label="Hide the analyst" title="Hide">
              <X class="w-3.5 h-3.5" aria-hidden="true" />
            </button>
          {/if}
        </div>
      {/if}
    </header>
    {#if dock === "rail" && messages.length === 0 && !operationBlocked}
      <p class="chat-head-copy">Ask about these findings, or tell me what to change.</p>
    {/if}
  {/if}

  <!-- A scrollable region needs to be reachable by keyboard (2.1.1) — the lint rule
       doesn't model that case, so it is silenced deliberately here. And the log must
       not re-announce on every streamed character: it goes quiet while a turn is in
       flight and speaks the settled reply when it lands. -->
  <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
  <div
    class="chat-list"
    bind:this={listEl}
    onscroll={onListScroll}
    tabindex="0"
    role="log"
    aria-label="Conversation"
    aria-busy={sending}
    aria-live={readOnly || sending ? "off" : "polite"}
  >
    {#if !historyLoaded}
      <p class="chat-status">Loading conversation&hellip;</p>
    {:else if loadFailed && showHistoryRetry}
      <!-- Exactly ONE retry per screen. SegmentedLedger renders its own banner and also mounts a
           live thread plus a read-only thread per past segment — so an unguarded retry here would
           put four or five identical Retry buttons on the page for a single failed fetch. The
           host that owns the failure message owns the retry. -->
      <p class="chat-status">
        Couldn't load the conversation.
        <button type="button" class="chat-retry" disabled={retryingHistory} onclick={retryHistory}>
          {#if retryingHistory}
            <Loader2 class="w-3 h-3 animate-spin" aria-hidden="true" />
            Retrying&hellip;
          {:else}
            Retry
          {/if}
        </button>
      </p>
    {:else}
      {#if messages.length === 0}
        <p class="chat-status">
          {operationBlocked
            ? "The conversation will unlock when research reaches the next checkpoint."
            : "No questions yet. Ask about scores, gaps, or what to try next."}
        </p>
      {/if}
      {#each messages as msg (msg.id)}
        {#if msg.role === "receipt" && msg.receipt}
          <!-- A receipt is the record of a change that LANDED: what it now says, and
               the one action that follows from it. -->
          <div class="entry entry-receipt">
            <div class="entry-body">
              <div class="receipt">
                <div class="receipt-head">
                  <Check class="receipt-icon" aria-hidden="true" />
                  <span class="receipt-title">Change applied</span>
                </div>
                <dl class="receipt-rows">
                  {#each msg.receipt.rows as row}
                    <div class="ledger-field">
                      <dt>{row.label}</dt>
                      <dd>{row.value}</dd>
                    </div>
                  {/each}
                </dl>
                <p class="receipt-note">{msg.receipt.note}</p>
              </div>
            </div>
          </div>
        {:else}
        <div class="entry entry-{msg.role}">
          <span class="entry-tag">{msg.role === "user" ? "You" : "Analyst response"}</span>
          <div class="entry-body">
            {#if msg.role === "assistant" && msg.toolCallsJson?.length}
              <ul class="tool-receipts">
                {#each msg.toolCallsJson as tc}
                  <li class="tool-receipt">
                    <Search class="tool-receipt-icon" aria-hidden="true" />
                    {tc.label}
                  </li>
                {/each}
              </ul>
            {/if}
            {#if msg.role === "assistant"}
              <div class="entry-prose">
                <IdeaReferenceText
                  content={msg.content}
                  references={ideaReferences}
                  onOpen={onOpenIdeaReference}
                  markdown
                />
              </div>
            {:else}
              <p class="entry-plain">{msg.content}</p>
            {/if}
            {#if msg.truncated}
              <p class="entry-note">Reply was interrupted.</p>
            {/if}
            {#if msg.patchJson && !msg.dismissed && !isLedgerEvent(msg.patchJson) && isSelectionCopilotAction(msg.patchJson)}
              {@const copilotAction = msg.patchJson}
              {@const copilotSupported = copilotPrefillSupported(copilotAction)}
              <div class="proposal copilot-card">
                <div class="proposal-head">
                  <Wand2 class="proposal-icon" aria-hidden="true" />
                  <span class="proposal-title">
                    {copilotAction.action === "prefill" ? "Draft prepared for review" : copilotAction.action === "shortlist_review" ? "Shortlist prepared for review" : "Workspace suggestion"}
                  </span>
                  <span class="proposal-scope">Review only</span>
                </div>

                {#if copilotAction.ideas.length}
                  <ul class="copilot-ideas" aria-label="Ideas referenced by this suggestion">
                    {#each copilotAction.ideas as idea (`${idea.ideaId}:${idea.ideaRevision}`)}
                      <li><strong>{idea.solutionName}</strong><span>Revision {idea.ideaRevision}</span></li>
                    {/each}
                  </ul>
                {/if}

                <p class="proposal-why">{copilotAction.rationale}</p>
                {#if copilotAction.caveats.length}
                  <div class="copilot-caveats">
                    <strong>Check before saving</strong>
                    <ul>{#each copilotAction.caveats as caveat}<li>{caveat}</li>{/each}</ul>
                  </div>
                {/if}
                <p class="proposal-note">Nothing has been changed. The existing form or shortlist confirmation is the only place that can save this.</p>

                {#if readOnly}
                  <p class="proposal-note">This action is available only in the owner workspace.</p>
                {:else}
                  <div class="proposal-actions">
                    <button
                      type="button"
                      class="ledger-btn ledger-btn--primary"
                      disabled={applying || operationBlocked || !onCopilotAction || !copilotSupported}
                      onclick={() => void handleCopilotAction(copilotAction, msg.id)}
                    >
                      {copilotButtonLabel(copilotAction)}
                    </button>
                  </div>
                  {#if !copilotSupported}
                    <p class="proposal-note proposal-note--warn">This draft type is not connected to a safe prefill yet. Open the workspace manually; no values were applied.</p>
                  {:else if copilotActionFeedback[msg.id]}
                    <p
                      class="proposal-note"
                      class:entry-error={copilotActionFeedback[msg.id].failed}
                      role={copilotActionFeedback[msg.id].failed ? "alert" : "status"}
                    >{copilotActionFeedback[msg.id].message}</p>
                  {/if}
                {/if}
              </div>
            {:else if msg.patchJson && !msg.dismissed && !isLedgerEvent(msg.patchJson) && isIdeaSynthesisPatch(msg.patchJson)}
              {@const synthesis = msg.patchJson}
              {@const synthesisResult = chatLedger.seedResult(msg.id)}
              {@const synthesisOutcome = chatLedger.seedOutcome(msg.id)}
              <div
                class="seed-card synthesis-card"
                class:seed-card--pending={synthesisOutcome === "pending"}
                class:seed-card--accepted={synthesisOutcome === "accepted"}
                class:seed-card--demoted={synthesisOutcome === "demoted"}
                class:seed-card--failed={synthesisOutcome === "failed" || synthesisOutcome === "refunded"}
                aria-busy={synthesisOutcome === "pending"}
              >
                <div class="seed-card-head" aria-live="polite" aria-atomic="true">
                  {#if synthesisOutcome === "accepted"}
                    <Check class="seed-card-icon seed-card-icon--accepted" aria-hidden="true" />
                    <span class="seed-card-title">Variant evaluated. Added to ranked ideas.</span>
                  {:else if synthesisOutcome === "demoted"}
                    <span class="seed-card-title">Variant evaluated. It didn't clear the market-fit bar.</span>
                  {:else if synthesisOutcome === "failed" || synthesisOutcome === "refunded"}
                    <span class="seed-card-title">Evaluation failed. Your credits were refunded.</span>
                  {:else if synthesisOutcome === "pending"}
                    <Loader2 class="seed-card-icon animate-spin" aria-hidden="true" />
                    <span class="seed-card-title">Evaluating the variant&hellip;</span>
                  {:else}
                    <Wand2 class="seed-card-icon" aria-hidden="true" />
                    <span class="seed-card-title">{SYNTHESIS_LABEL[synthesis.operation]} candidate</span>
                  {/if}
                </div>

                <dl class="seed-card-fields">
                  <div class="ledger-field">
                    <dt>Proposed candidate</dt>
                    <dd><strong>{synthesis.proposedTitle}</strong><br />{synthesis.proposedBrief}</dd>
                  </div>
                  <div class="ledger-field">
                    <dt>What changes</dt>
                    <dd>{synthesis.changeSummary}</dd>
                  </div>
                  {#each synthesis.parents as parent}
                    <div class="ledger-field">
                      <dt>Retain from {parent.solutionName}</dt>
                      <dd>{parent.contribution}</dd>
                    </div>
                  {/each}
                </dl>
                <p class="seed-card-why">{synthesis.rationale}</p>

                <details class="synthesis-evidence">
                  <summary>Evidence and assumptions to re-check</summary>
                  <ul>
                    {#each synthesis.evidence.requiresValidation as item}
                      <li>{item}</li>
                    {/each}
                  </ul>
                </details>
                <p class="proposal-note">The source candidates stay unchanged. Their scores do not carry over to this variant.</p>

                {#if synthesisOutcome === "accepted" || synthesisOutcome === "demoted"}
                  <div class="seed-card-result">
                    <span class="seed-card-result-label">Evaluated result</span>
                    {#if synthesisResult}
                      <strong>{synthesisResult.solution_name}</strong>
                      {#if synthesisResult.short_description}
                        <p>{synthesisResult.short_description}</p>
                      {/if}
                      {#if synthesisResult.market_fit_score != null}
                        <span class="seed-card-result-score">Market fit {Math.round(synthesisResult.market_fit_score * 100)}%</span>
                      {/if}
                    {:else}
                      <p>{synthesisOutcome === "accepted" ? "The evaluated variant is in your ranked ideas." : "The evaluated variant is in Examined & ruled out."}</p>
                    {/if}
                    {#if !readOnly}
                      <a
                        class="seed-card-result-link"
                        href={synthesisOutcome === "accepted" ? "#solution-selector" : "#examined-ruled-out"}
                        onclick={() => onCollapse?.()}
                      >
                        {synthesisOutcome === "accepted" ? "View evaluated candidate" : "View why it was ruled out"}
                        <ArrowRight aria-hidden="true" />
                      </a>
                    {/if}
                  </div>
                  {#if !readOnly && synthesisOutcome === "accepted" && synthesisResult && (onReviewVariant || onUseVariant)}
                    <div class="proposal-actions">
                      {#if onReviewVariant}
                        <button
                          type="button"
                          class="ledger-btn ledger-btn--ghost"
                          disabled={applying || operationBlocked}
                          onclick={() => handleVariantAction("review", synthesis, synthesisResult, msg.id)}
                        >
                          {synthesis.parents.length === 2 ? "Compare with sources" : "Compare with source"}
                        </button>
                      {/if}
                      {#if onUseVariant}
                        <button
                          type="button"
                          class="ledger-btn ledger-btn--primary"
                          disabled={applying || operationBlocked}
                          onclick={() => handleVariantAction("use", synthesis, synthesisResult, msg.id)}
                        >
                          Use variant in shortlist
                        </button>
                      {/if}
                    </div>
                    {#if variantActionFeedback[msg.id]}
                      <p
                        class="proposal-note"
                        class:entry-error={variantActionFeedback[msg.id].failed}
                        role={variantActionFeedback[msg.id].failed ? "alert" : "status"}
                      >{variantActionFeedback[msg.id].message}</p>
                    {/if}
                  {/if}
                {/if}

                {#if readOnly}
                  <p class="proposal-note">Proposed here, never evaluated.</p>
                {:else if !synthesisOutcome}
                  <div class="proposal-actions">
                    <button
                      type="button"
                      class="ledger-btn ledger-btn--primary seed-card-evaluate"
                      disabled={applying || operationBlocked || seedCost == null}
                      onclick={() => applyPatch(msg)}
                    >
                      <span>Evaluate variant</span>
                      {#if seedCost != null}
                        <span class="seed-card-cost"><Coins class="w-3 h-3" aria-hidden="true" />{seedCost}</span>
                      {/if}
                    </button>
                    <button type="button" class="ledger-btn ledger-btn--ghost" disabled={applying} onclick={() => dismissPatch(msg)}>
                      Dismiss
                    </button>
                  </div>
                  {#if seedCost == null}
                    <p class="proposal-note">Price hasn't loaded yet. Try again in a moment.</p>
                  {/if}
                {:else if synthesisOutcome === "pending"}
                  <p class="proposal-note">The variant is being scored independently; this can take a few minutes.</p>
                {/if}
              </div>
            <!-- The user-composed idea seed gets its OWN card — not the generic
                 before→after diff table (a free-text idea has nothing to diff), and
                 its terminal state is durable (chatLedger.seedOutcome), never a
                 parallel client store, so a submitted card can never re-arm. -->
            {:else if msg.patchJson && !msg.dismissed && !isLedgerEvent(msg.patchJson) && isNewIdeaSeedPatch(msg.patchJson)}
              {@const seedPatch = msg.patchJson}
              {@const seedResult = chatLedger.seedResult(msg.id)}
              {@const seedOutcome = chatLedger.seedOutcome(msg.id)}
              <div
                class="seed-card"
                class:seed-card--pending={seedOutcome === "pending"}
                class:seed-card--accepted={seedOutcome === "accepted"}
                class:seed-card--demoted={seedOutcome === "demoted"}
                class:seed-card--failed={seedOutcome === "failed" || seedOutcome === "refunded"}
                aria-busy={seedOutcome === "pending"}
              >
                <div class="seed-card-head" aria-live="polite" aria-atomic="true">
                  {#if seedOutcome === "accepted"}
                    <Check class="seed-card-icon seed-card-icon--accepted" aria-hidden="true" />
                    <span class="seed-card-title">Evaluation complete. Added to ranked ideas.</span>
                  {:else if seedOutcome === "demoted"}
                    <span class="seed-card-title">We tested your idea. It didn't clear the market-fit bar.</span>
                  {:else if seedOutcome === "failed" || seedOutcome === "refunded"}
                    <span class="seed-card-title">Evaluation failed. Your credits were refunded.</span>
                  {:else if seedOutcome === "pending"}
                    <Loader2 class="seed-card-icon animate-spin" aria-hidden="true" />
                    <span class="seed-card-title">Evaluating your idea&hellip;</span>
                  {:else}
                    <Wand2 class="seed-card-icon" aria-hidden="true" />
                    <span class="seed-card-title">Review your idea</span>
                  {/if}
                </div>

                <dl class="seed-card-fields">
                  <div class="ledger-field">
                    <dt>Idea</dt>
                    <dd>{seedPatch.free_text}</dd>
                  </div>
                  {#if seedPatch.pain_ref}
                    <div class="ledger-field">
                      <dt>Evaluation anchor</dt>
                      <dd>{seedPatch.pain_ref}</dd>
                    </div>
                  {/if}
                  {#if seedPatch.tool_ref}
                    <div class="ledger-field">
                      <dt>Tool referenced</dt>
                      <dd>{seedPatch.tool_ref}</dd>
                    </div>
                  {/if}
                </dl>
                <p class="seed-card-why">{seedPatch.rationale}</p>
                {#if seedOutcome === "accepted" || seedOutcome === "demoted"}
                  <div class="seed-card-result">
                    <span class="seed-card-result-label">Evaluated result</span>
                    {#if seedResult}
                      <strong>{seedResult.solution_name}</strong>
                      {#if seedResult.short_description}
                        <p>{seedResult.short_description}</p>
                      {/if}
                      {#if seedResult.market_fit_score != null}
                        <span class="seed-card-result-score">Market fit {Math.round(seedResult.market_fit_score * 100)}%</span>
                      {/if}
                    {:else}
                      <p>{seedOutcome === "accepted" ? "The evaluated result is in your ranked ideas." : "The evaluated result is in Examined & ruled out."}</p>
                    {/if}
                    {#if !readOnly}
                      <a
                        class="seed-card-result-link"
                        href={seedOutcome === "accepted" ? "#solution-selector" : "#examined-ruled-out"}
                        onclick={() => onCollapse?.()}
                      >
                        {seedOutcome === "accepted" ? "View full candidate details" : "View why it was ruled out"}
                        <ArrowRight aria-hidden="true" />
                      </a>
                    {/if}
                  </div>
                {/if}

                {#if readOnly}
                  <p class="proposal-note">Proposed here, never evaluated.</p>
                {:else if !seedOutcome}
                  <div class="proposal-actions">
                    <button
                      type="button"
                      class="ledger-btn ledger-btn--primary seed-card-evaluate"
                      disabled={applying || operationBlocked || seedCost == null}
                      onclick={() => applyPatch(msg)}
                    >
                      <span>Evaluate my idea</span>
                      {#if seedCost != null}
                        <span class="seed-card-cost"><Coins class="w-3 h-3" aria-hidden="true" />{seedCost}</span>
                      {/if}
                    </button>
                    <button type="button" class="ledger-btn ledger-btn--ghost" disabled={applying} onclick={() => dismissPatch(msg)}>
                      Dismiss
                    </button>
                  </div>
                  {#if seedCost == null}
                    <p class="proposal-note">Price hasn't loaded yet. Try again in a moment.</p>
                  {/if}
                {:else if seedOutcome === "pending"}
                  <p class="proposal-note">This runs the same evaluation as a pool idea. It can take a few minutes.</p>
                {/if}
              </div>
            <!-- Ledger-event payloads ride on 'receipt' rows (rendered above), never
                 as proposal cards — exclude them so a durable receipt can't be
                 mistaken for a live proposal. -->
            {:else if msg.patchJson && !msg.dismissed && !isLedgerEvent(msg.patchJson)}
              {@const isApplied = appliedPatchIds.has(msg.id)}
              {@const gate = isGatePatch(msg.patchJson)}
              {@const rows = proposalRows(msg.patchJson)}
              <!-- A proposal is a decision put to you: it says what it changes, what
                   that costs, and gives you exactly two answers. -->
              <div class="proposal" class:is-applied={isApplied}>
                <div class="proposal-head">
                  {#if isApplied}
                    <Check class="proposal-icon proposal-icon--applied" aria-hidden="true" />
                    <span class="proposal-title">Change applied</span>
                  {:else}
                    <Wand2 class="proposal-icon" aria-hidden="true" />
                    <span class="proposal-title">Proposed change</span>
                    {#if !readOnly}
                      <span class="proposal-scope">
                        {gate ? "Re-runs this checkpoint" : "Steers the next batch"}
                      </span>
                    {/if}
                  {/if}
                </div>

                <dl class="proposal-diff">
                  {#each rows as row (row.label)}
                    <div class="ledger-field">
                      <dt>{row.label}</dt>
                      <dd>
                        <span class="proposal-before">{row.before}</span>
                        <ArrowRight class="proposal-arrow" aria-hidden="true" />
                        <span class="proposal-after">{row.after}</span>
                      </dd>
                    </div>
                  {/each}
                </dl>

                <p class="proposal-why">{msg.patchJson.rationale}</p>

                {#if isApplied}
                  <p class="proposal-note proposal-note--applied">
                    The framing above now reflects this change.
                  </p>
                {:else if readOnly}
                  <p class="proposal-note">Proposed here. Never applied.</p>
                {:else}
                  <div class="proposal-actions">
                    <button
                      type="button"
                      class="ledger-btn ledger-btn--primary proposal-apply"
                      class:is-busy={applying}
                      disabled={applying || operationBlocked || (gate && applyCapReached)}
                      onclick={() => applyPatch(msg)}
                    >
                      {#if applying}
                        <Loader2 class="w-3.5 h-3.5 animate-spin" aria-hidden="true" />
                        Applying&hellip;
                      {:else}
                        Apply changes
                      {/if}
                    </button>
                    <button type="button" class="ledger-btn ledger-btn--ghost" disabled={applying} onclick={() => dismissPatch(msg)}>
                      Keep as is
                    </button>
                  </div>
                  {#if gate && applyCapReached}
                    <p class="proposal-note proposal-note--warn">
                      Change limit reached for this checkpoint (5 max). Continue research to move forward.
                    </p>
                  {/if}
                {/if}
              </div>
            {/if}
          </div>
        </div>
        {/if}
      {/each}
      {#if sending}
        <div class="entry entry-assistant entry-pending">
          <span class="entry-tag">Analyst response</span>
          <div class="entry-body">
            {#if pendingToolLabels.length}
              <ul class="tool-receipts">
                {#each pendingToolLabels as label}
                  <li class="tool-receipt">
                    <Search class="tool-receipt-icon" aria-hidden="true" />
                    {label}
                  </li>
                {/each}
              </ul>
            {/if}
            {#if hasStreamStarted}
              <p class="entry-plain">{streamingContent}<span class="ledger-caret" aria-hidden="true"></span></p>
            {:else}
              <p class="entry-pending-line">
                {pendingToolLabels.length ? "Reviewing retrieved evidence" : "Reading the dossier"}<span
                  class="ledger-caret"
                  aria-hidden="true"
                ></span>
              </p>
            {/if}
          </div>
        </div>
      {/if}

      <!-- Suggestions belong to the answer they follow. Keeping them in the transcript
           lets them scroll away instead of permanently reducing the composer viewport. -->
      {#if activeStarters.length > 0 && !locked && !sending && historyLoaded && !atTurnCap && !operationBlocked && !loadFailed}
        <div class="followups" role="group" aria-label="Suggested questions">
          <h3 class="followups-title">Continue exploring</h3>
          {#each activeStarters as chip (chip)}
            <button type="button" class="followup" onclick={() => prefillStarter(chip)}>
              <span>{chip}</span>
              <ArrowRight class="followup-icon" aria-hidden="true" />
            </button>
          {/each}
        </div>
      {/if}
    {/if}
  </div>

  {#if !readOnly}
  <!-- Scrolled up mid-stream? The answer keeps coming, but we don't drag you to it. -->
  {#if !stickToBottom && messages.length > 0}
    <div class="chat-jump-row">
      <button type="button" class="chat-jump" onclick={jumpToLatest}>
        <ArrowDown class="w-3 h-3" aria-hidden="true" />
        Jump to latest
      </button>
    </div>
  {/if}

  {#if locked}
    <p class="chat-status chat-status--locked" role="status">Guided chat is a subscriber feature. Upgrade to ask the analyst about these ideas.</p>
  {:else if operationBlocked}
    <div class="chat-operation" role="status" aria-live="polite">
      <span class="chat-operation-pulse" aria-hidden="true"></span>
      <span class="chat-operation-copy">
        <strong>{blockedTitle}</strong>
        <span>{blockedDetail}</span>
      </span>
    </div>
  {:else if sendError}
    <p class="chat-error" role="alert">
      {sendError}
      {#if failedDraft}
        <button type="button" class="chat-retry" onclick={() => { input = failedDraft; pendingSynthesisIntent = failedSynthesisIntent; sendError = ""; failedDraft = ""; failedSynthesisIntent = null; void send(); }}>
          Retry
        </button>
      {/if}
    </p>
  {:else if sendNote}
    <p class="chat-note" role="status">{sendNote}</p>
  {/if}

  {#if atTurnCap && !readOnly}
    <p class="chat-cap" role="status">
      You've used all {maxTurns} questions for this run. The analyst is done here. You can still
      continue the research or pick an idea.
    </p>
  {/if}

  {#if !operationBlocked}
    <div class="chat-input">
      <Composer
        bind:this={composerRef}
        bind:value={input}
        placeholder="Ask a follow-up or request a change…"
        label="Message the analyst"
        disabled={locked || !historyLoaded || atTurnCap || loadFailed}
        busy={sending}
        size={focused ? "roomy" : "compact"}
        onSubmit={() => void send()}
        onStop={stopStreaming}
      />
    </div>
  {/if}
  {/if}
</aside>

<style>
  .chat-thread {
    --chat-motion: cubic-bezier(0.32, 0.72, 0, 1);
    /* Warm parchment tint — the ledger's own identity. No dedicated token exists
       for it, and no raw hex is allowed: the warmth is the amber warning token
       (the palette's closest warm hue) folded into the real bg tokens at low
       strength, so it tracks any future palette change instead of drifting. */
    --chat-warm-tint: color-mix(in srgb, var(--color-warning) 26%, var(--color-bg-elevated));
    --chat-paper: color-mix(in srgb, var(--color-bg-elevated) 96%, var(--chat-warm-tint));
    --chat-wash: color-mix(in srgb, var(--color-bg-surface) 92%, var(--chat-warm-tint));
    display: flex;
    flex-direction: column;
    gap: 0;
    min-height: 0;
    background: var(--chat-paper);
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 52%, transparent);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
    overflow: hidden;
  }
  .chat-thread--rail {
    animation: chat-rail-in 240ms var(--chat-motion) both;
  }
  /* Archived-segment rendering (SegmentedLedger): flat, quiet, motionless — the
     surrounding panel owns the chrome; history is read, not used. */
  .chat-thread--readonly {
    background: transparent;
    border: 0;
    border-radius: 0;
    box-shadow: none;
    animation: none;
  }
  .chat-thread--readonly .chat-list {
    min-height: 0;
    border-top: 0;
  }
  .chat-thread--readonly .entry-receipt {
    animation: none;
  }
  .chat-thread--readonly .receipt {
    background: color-mix(in srgb, var(--color-success) 4%, transparent);
    border-color: color-mix(in srgb, var(--color-success) 20%, transparent);
  }
  /* Main dock (GateWorkbench + read-only transcript): same conversation grammar as
     the window — no divider rows, a byline for the analyst, a card for your turn —
     with the measure capped so prose doesn't run 95 characters across the column. */
  .chat-thread--main .entry {
    display: block;
    padding: var(--space-3) var(--space-5);
    border-bottom: 0;
  }
  .chat-thread--main .entry-user .entry-body {
    max-width: 85%;
    margin-left: auto;
  }
  .chat-thread--main .entry-user .entry-plain {
    padding: var(--space-2) var(--space-3);
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg) var(--radius-lg) var(--radius-sm) var(--radius-lg);
  }
  .chat-thread--main .entry-assistant .entry-tag,
  .chat-thread--main .entry-receipt .entry-tag {
    display: block;
    margin-bottom: var(--space-1-5);
    padding-top: 0;
    letter-spacing: 0.08em;
  }
  .chat-thread--main .entry-prose,
  .chat-thread--main .entry-plain,
  .chat-thread--main .entry-pending-line {
    font-size: 0.9375rem;
    line-height: 1.6;
    max-width: 34rem;
  }

  .chat-thread--main {
    background: transparent;
    border: 0;
    border-radius: 0;
    box-shadow: none;
  }
  .chat-thread--main .chat-head {
    border-top: 1px solid var(--color-border);
    padding: var(--space-3) var(--space-5) var(--space-2);
  }
  .chat-thread--main .chat-list {
    min-height: 0;
    border-top: 0;
  }
  .chat-thread--main .entry,
  .chat-thread--main .chat-status {
    padding-left: var(--space-5);
    padding-right: var(--space-5);
  }
  .chat-thread--main .chat-input,
  .chat-thread--main .chat-error,
  .chat-thread--main .chat-status--locked,
  .chat-thread--main .chat-operation {
    padding-left: var(--space-5);
    padding-right: var(--space-5);
  }
  @keyframes chat-rail-in {
    from { opacity: 0; clip-path: inset(0 0 0 100%); }
    to { opacity: 1; clip-path: inset(0 0 0 0%); }
  }
  @media (prefers-reduced-motion: reduce) {
    .chat-thread--rail { animation: none; }
  }

  .chat-head {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    min-height: 3.5rem;
    padding: var(--space-2) var(--space-3) var(--space-2) var(--space-4);
    border-bottom: 1px solid var(--color-border);
    background: color-mix(in srgb, var(--chat-wash) 72%, transparent);
  }
  .chat-head-count {
    display: inline-flex;
    align-items: baseline;
    gap: 0.3rem;
    white-space: nowrap;
    font-family: var(--font-mono);
    font-size: 0.625rem;
    color: var(--color-text-muted);
    font-variant-numeric: tabular-nums;
  }
  .chat-head-count-value {
    font-size: 0.75rem;
    font-weight: 700;
    color: var(--color-text-secondary);
  }
  .chat-head-count-copy {
    font-weight: 500;
  }
  .chat-head-copy {
    margin: var(--space-1) var(--space-3) var(--space-3);
    font-size: 0.75rem;
    line-height: 1.4;
    color: var(--color-text-muted);
  }

  /* ═══ Title bar ═══
     Grounding is a provenance statement, not an online-presence dot. The title
     therefore owns the line while the evidence badge states why it can be trusted. */
  .chat-identity {
    display: grid;
    gap: 0.125rem;
    min-width: 0;
    margin-right: auto;
  }
  .chat-title-line {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    min-width: 0;
  }
  .chat-title {
    font-family: var(--font-display);
    font-size: 0.9375rem;
    font-weight: 700;
    line-height: 1.15;
    letter-spacing: -0.02em;
    color: var(--color-text-primary);
  }
  /* House .tag recipe (DESIGN_SYSTEM.md §tags): 10px mono outline chip, never a
     filled pill. Was a bespoke 9px accent-tinted badge — off the type scale. */
  .chat-grounding {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    padding: 0.125rem 0.5rem;
    border: 1px solid color-mix(in srgb, currentColor 40%, transparent);
    border-radius: var(--radius-md);
    color: var(--color-accent-dark);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    white-space: nowrap;
  }
  .chat-grounding :global(.chat-grounding-icon) {
    width: 0.625rem;
    height: 0.625rem;
    stroke-width: 2;
  }
  .chat-subtitle {
    overflow: hidden;
    font-family: var(--font-body);
    font-size: 0.625rem;
    font-weight: 500;
    color: var(--color-text-muted);
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* Panel controls — quiet until you look for them. */
  .chat-head-actions {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    margin-left: var(--space-1-5);
  }
  .chat-head-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2rem;
    background: transparent;
    border: 0;
    border-radius: var(--radius-md);
    color: var(--color-text-muted);
    cursor: pointer;
    transition: background 150ms var(--chat-motion), color 150ms var(--chat-motion),
      transform 150ms var(--chat-motion);
  }
  .chat-head-btn:hover {
    background: var(--color-bg-surface);
    color: var(--color-text-primary);
  }
  .chat-head-btn:active {
    transform: scale(0.94);
  }
  .chat-head-btn:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 1px;
  }

  /* Jump to latest — the stream kept going while you read; this is the way back. */
  .chat-jump-row {
    display: flex;
    justify-content: center;
    padding: var(--space-1-5) 0 0;
  }
  .chat-jump {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    padding: var(--space-1) var(--space-3);
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border-emphasis);
    border-radius: 9999px;
    box-shadow: var(--shadow-sm);
    color: var(--color-text-secondary);
    font-family: var(--font-body);
    font-size: 0.6875rem;
    font-weight: 700;
    min-height: 1.75rem;
    cursor: pointer;
    transition: color 150ms var(--chat-motion), transform 150ms var(--chat-motion);
  }
  .chat-jump:hover {
    color: var(--color-text-primary);
  }
  .chat-jump:active {
    transform: scale(0.96);
  }
  .chat-jump:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  @media (prefers-reduced-motion: reduce) {
    .chat-head-btn,
    .chat-jump,
    .followup { transition: none; }
    .chat-head-btn:active,
    .chat-jump:active,
    .proposal-dismiss:active:not(:disabled) { transform: none; }
  }

  .chat-list {
    display: flex;
    flex-direction: column;
    min-height: 8rem;
    max-height: 26rem;
    overflow-y: auto;
    border-top: 1px solid var(--color-border);
    background:
      radial-gradient(circle at 50% 0, color-mix(in srgb, var(--color-accent) 3%, transparent), transparent 30rem),
      var(--chat-paper);
    scroll-behavior: smooth;
  }
  /* Docked/focus panels own their height from the outside — the list fills whatever
     the panel gives it instead of stopping dead at 26rem with dead space below. */
  .chat-thread--rail .chat-list {
    max-height: none;
    /* Scrolled text shouldn't be guillotined mid-letter at the composer seam: the
       last line fades out, which also reads as "there is more above/below". */
    mask-image: linear-gradient(to bottom, transparent 0, black 0.75rem, black calc(100% - 1rem), transparent 100%);
  }
  .chat-status {
    margin: 0;
    padding: var(--space-4) var(--space-3);
    font-size: 0.75rem;
    line-height: 1.45;
    color: var(--color-text-secondary);
  }
  /* Standalone use (below the list, next to the input) — a persistent notice
     rather than a placeholder that would otherwise replace already-loaded
     messages when entitlement is lost mid-conversation (send() sets `locked`,
     not the history load — see ChatThread's script block). */
  .chat-status--locked {
    padding: var(--space-1-5) var(--space-3) 0;
    color: var(--color-text-secondary);
  }
  .chat-operation {
    position: relative;
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    align-items: center;
    gap: var(--space-3);
    min-height: 4.25rem;
    padding: var(--space-3) var(--space-4);
    overflow: hidden;
    border-top: 1px solid var(--color-border);
    background: color-mix(in srgb, var(--chat-wash) 82%, transparent);
  }
  .chat-operation::after {
    content: "";
    position: absolute;
    inset: auto 0 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, var(--color-accent), transparent);
    transform: translateX(-100%);
    animation: chat-operation-track 1.8s var(--chat-motion) infinite;
  }
  @keyframes chat-operation-track {
    to { transform: translateX(100%); }
  }
  .chat-operation-pulse {
    position: relative;
    width: 0.625rem;
    height: 0.625rem;
    border-radius: 50%;
    background: var(--color-accent);
  }
  .chat-operation-pulse::after {
    content: "";
    position: absolute;
    inset: -0.3rem;
    border: 1px solid color-mix(in srgb, var(--color-accent) 38%, transparent);
    border-radius: inherit;
    animation: chat-operation-pulse 1.8s ease-out infinite;
  }
  @keyframes chat-operation-pulse {
    0% { opacity: 0.85; transform: scale(0.65); }
    75%, 100% { opacity: 0; transform: scale(1.35); }
  }
  .chat-operation-copy {
    display: grid;
    gap: 0.15rem;
    min-width: 0;
  }
  .chat-operation-copy strong {
    font-family: var(--font-display);
    font-size: 0.8125rem;
    font-weight: 700;
    color: var(--color-text-primary);
  }
  .chat-operation-copy span {
    font-size: 0.6875rem;
    line-height: 1.4;
    color: var(--color-text-muted);
  }

  .entry {
    display: grid;
    grid-template-columns: var(--ledger-tag-col) minmax(0, 1fr);
    gap: var(--space-2);
    padding: 0.6rem var(--ledger-gutter);
    border-bottom: 1px solid var(--color-border);
  }
  /* ═══ Conversation rhythm ═══
     The old treatment made every turn an identical full-width row divided by a
     hairline: a table of speech, not a conversation. Speakers now differ in KIND —
     your question is a compact card addressed to the analyst; the analyst's answer
     is open prose that owns the column, the way a written reply does. No dividers:
     rhythm comes from the alternation itself. */
  .chat-thread--rail .entry {
    display: block;
    padding: var(--space-3) var(--space-4);
    border-bottom: 0;
    animation: entry-in 200ms var(--chat-motion) both;
  }
  @keyframes entry-in {
    from { opacity: 0; transform: translateY(3px); }
    to { opacity: 1; transform: translateY(0); }
  }
  @media (prefers-reduced-motion: reduce) {
    .chat-thread--rail .entry { animation: none; }
  }

  /* Your turn: right-weighted, contained, quiet. */
  .chat-thread--rail .entry-user {
    padding-bottom: var(--space-1-5);
  }
  /* The bubble and the alignment carry the speaker VISUALLY; a screen reader still
     needs the byline, so it is hidden, not deleted. */
  .chat-thread--rail .entry-user .entry-tag {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip-path: inset(50%);
    white-space: nowrap;
    border: 0;
  }
  .chat-thread--rail .entry-user .entry-body {
    max-width: 85%;
    margin-left: auto;
  }
  .chat-thread--rail .entry-user .entry-plain {
    padding: var(--space-2) var(--space-3);
    background: color-mix(in srgb, var(--color-accent) 3%, var(--chat-wash));
    border: 1px solid color-mix(in srgb, var(--color-accent) 10%, var(--color-border));
    /* Squared toward the speaker — a tail without drawing a tail. */
    border-radius: var(--radius-lg) var(--radius-lg) var(--radius-sm) var(--radius-lg);
    color: var(--color-text-primary);
    text-align: left;
  }

  /* The analyst's turn: a byline, then prose. Nothing boxed — the answer is the
     content of the panel, not an object inside it. */
  .chat-thread--rail .entry-assistant .entry-tag,
  .chat-thread--rail .entry-receipt .entry-tag {
    display: block;
    margin-bottom: var(--space-1-5);
    padding-top: 0;
    font-family: var(--font-body);
    font-size: 0.6875rem;
    font-weight: 600;
    letter-spacing: 0.015em;
    color: var(--color-text-secondary);
  }
  /* Long-form measure guard: past ~75 characters per line the eye loses the return
     sweep. The cap must sit on the TEXT elements — `ch` on the wrapper resolves
     against the inherited 17px body size, not the 13px prose, and silently computes
     to ~900px. */
  /* Docked = a companion window, so it runs one step DOWN the type scale: the panel
     is ~26rem wide, and body-size prose in it reads like a blown-up phone mock.
     Full-size (below) steps back up, where there's room for it. Caps are in rem, not
     ch: `ch` measures the "0" glyph of whichever font-size is in scope, which in a
     proportional face + inherited 17px wrapper silently resolved to ~900px. */
  .chat-thread--rail .entry-prose,
  .chat-thread--rail .entry-plain,
  .chat-thread--rail .entry-pending-line {
    max-width: 30rem;
    font-size: 0.75rem;
    line-height: 1.55;
  }

  /* Focus: a reading view, not just a bigger box. The window may be wide, but the
     text is not: every zone centres on ONE column, so the eye tracks a single left
     edge from the answer to the composer. */
  .chat-thread--focus .entry,
  .chat-thread--focus .chat-status,
  .chat-thread--focus .followups {
    width: min(48rem, 100%);
    margin-inline: auto;
  }
  .chat-thread--focus .entry,
  .chat-thread--focus .chat-status {
    padding: var(--space-5) var(--space-6);
  }
  .chat-thread--focus .entry-user {
    padding-top: var(--space-4);
    padding-bottom: var(--space-2);
  }
  .chat-thread--focus .entry-user .entry-body {
    max-width: 42rem;
  }
  .chat-thread--focus .entry-user .entry-plain {
    padding: 0.8rem 1rem;
    border-radius: 0.875rem 0.875rem 0.3125rem 0.875rem;
    box-shadow: inset 0 1px 0 color-mix(in srgb, white 64%, transparent);
  }
  .chat-thread--focus .chat-input {
    display: grid;
    justify-items: stretch;
  }
  .chat-thread--focus .chat-input > :global(*) {
    width: min(48rem, 100%);
    margin-inline: auto;
  }
  /* Roughly 65–72 characters per line: long enough for research prose without
     making the return sweep tiring. */
  .chat-thread--focus .entry-prose,
  .chat-thread--focus .entry-plain {
    max-width: 42rem;
    font-size: 0.9375rem;
    line-height: 1.62;
    text-wrap: pretty;
  }
  .chat-thread--focus .entry-user .entry-plain {
    font-size: 0.875rem;
    line-height: 1.55;
  }

  /* Rendered chat Markdown needs its own compact reading rhythm. Tailwind resets
     list markers, and markers positioned outside an unpadded list are clipped by
     the scroll viewport, so both the marker style and its inset are explicit. */
  .entry-prose {
    overflow-wrap: anywhere;
  }
  .entry-prose :global(p) {
    margin: 0 0 0.78em;
  }
  .entry-prose :global(p:last-child) {
    margin-bottom: 0;
  }
  .entry-prose :global(h2),
  .entry-prose :global(h3),
  .entry-prose :global(h4) {
    margin: 1.15em 0 0.45em;
    color: var(--color-text-primary);
    font-family: var(--font-display);
    font-weight: 600;
    line-height: 1.3;
    letter-spacing: -0.015em;
  }
  .entry-prose :global(h2) {
    font-size: 1.0625em;
  }
  .entry-prose :global(h3),
  .entry-prose :global(h4) {
    font-size: 1em;
  }
  .entry-prose :global(ul),
  .entry-prose :global(ol) {
    margin: 0.65em 0 0.9em;
    padding-inline-start: 1.5rem;
    list-style-position: outside;
  }
  .entry-prose :global(ul) {
    list-style-type: disc;
  }
  .entry-prose :global(ol) {
    list-style-type: decimal;
  }
  .entry-prose :global(li) {
    margin: 0.32em 0;
    padding-inline-start: 0.18rem;
  }
  .entry-prose :global(li::marker) {
    color: var(--color-text-muted);
    font-weight: 600;
  }
  .entry-prose :global(li > p) {
    margin-bottom: 0.35em;
  }
  .entry-prose :global(ul ul),
  .entry-prose :global(ul ol),
  .entry-prose :global(ol ul),
  .entry-prose :global(ol ol) {
    margin: 0.3em 0;
    padding-inline-start: 1.2rem;
  }
  .entry-prose :global(strong) {
    color: var(--color-text-primary);
    font-weight: 600;
  }
  .chat-thread--focus .chat-list {
    padding-bottom: var(--space-2);
    mask-image: none;
  }
  .chat-thread--focus .chat-input {
    padding-left: var(--space-6);
    padding-right: var(--space-6);
  }
  .chat-thread--focus .chat-head {
    min-height: 4.25rem;
    padding: var(--space-3) var(--space-5) var(--space-3) var(--space-6);
  }
  .chat-thread--focus .chat-title {
    font-size: 1.0625rem;
  }
  .chat-thread--focus .chat-subtitle {
    font-size: 0.6875rem;
  }
  .chat-thread--focus .chat-head-count {
    font-size: 0.6875rem;
  }
  .chat-thread--focus .chat-head-count-value {
    font-size: 0.8125rem;
  }
  .chat-thread--focus .chat-head-btn {
    width: 2.25rem;
    height: 2.25rem;
  }
  .chat-list > .entry:last-child {
    border-bottom: 0;
  }
  .entry-tag {
    padding-top: var(--space-1);
    font-family: var(--font-body);
    font-size: 0.625rem;
    font-weight: 600;
    letter-spacing: 0.015em;
    color: var(--color-text-muted);
  }
  .entry-user .entry-tag {
    color: var(--color-text-secondary);
  }

  /* ── Applied-change receipt (ledger entry) ── */
  .entry-receipt {
    animation: receipt-in 240ms var(--chat-motion) both;
  }
  @keyframes receipt-in {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: translateY(0); }
  }
  @media (prefers-reduced-motion: reduce) {
    .entry-receipt { animation: none; }
  }
  /* ═══ Receipt — a change that LANDED ═══ */
  .receipt {
    display: grid;
    gap: var(--space-2);
    padding: var(--space-3) var(--space-3);
    background: color-mix(in srgb, var(--color-success) 5%, var(--color-bg-elevated));
    border: 1px solid color-mix(in srgb, var(--color-success) 26%, transparent);
    border-radius: var(--radius-lg);
  }
  .receipt-head {
    display: flex;
    align-items: center;
    gap: var(--space-1-5);
  }
  .receipt :global(.receipt-icon) {
    width: 0.875rem;
    height: 0.875rem;
    color: var(--color-success-text);
  }
  .receipt-title {
    font-family: var(--font-display);
    font-size: 0.8125rem;
    font-weight: 700;
    color: var(--color-success-text);
  }
  .receipt-rows {
    display: grid;
    gap: var(--space-1-5);
    margin: 0;
  }  .receipt-note {
    margin: 0;
    font-size: 0.75rem;
    line-height: 1.45;
    color: var(--color-text-secondary);
  }
  /* ═══ Proposal — a decision put to you ═══
     Titled, so you know what kind of object it is; the diff is the argument; the
     two buttons are the two answers. Orange sits on Apply alone — the one place a
     click changes the research. */
  .proposal {
    display: grid;
    gap: var(--space-2);
    margin-top: var(--space-2);
    padding: var(--space-3) var(--space-3);
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border-emphasis);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
  }
  .proposal.is-applied {
    background: color-mix(in srgb, var(--color-success) 4%, var(--color-bg-elevated));
    border-color: color-mix(in srgb, var(--color-success) 24%, transparent);
    box-shadow: none;
  }
  .proposal-head {
    display: flex;
    align-items: center;
    gap: var(--space-1-5);
  }
  .proposal :global(.proposal-icon) {
    width: 0.875rem;
    height: 0.875rem;
    color: var(--color-accent-dark);
  }
  .proposal :global(.proposal-icon--applied) {
    color: var(--color-success-text);
  }
  .proposal-title {
    font-family: var(--font-display);
    font-size: 0.8125rem;
    font-weight: 700;
    color: var(--color-text-primary);
  }
  .proposal.is-applied .proposal-title {
    color: var(--color-success-text);
  }
  /* What it costs you, stated before you decide — not after. */
  .proposal-scope {
    margin-left: auto;
    padding: var(--space-1) var(--space-2);
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-full, 9999px);
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    color: var(--color-text-secondary);
    white-space: nowrap;
  }

  .proposal-diff {
    display: grid;
    gap: var(--space-2);
    margin: 0;
    padding: var(--space-2) var(--space-3);
    background: color-mix(in srgb, var(--color-bg-surface) 70%, transparent);
    border-radius: var(--radius-md);
  }  .proposal-before {
    color: var(--color-text-muted);
    text-decoration: line-through;
    text-decoration-color: color-mix(in srgb, var(--color-text-muted) 55%, transparent);
    word-break: break-word;
  }
  .proposal :global(.proposal-arrow) {
    width: 0.7rem;
    height: 0.7rem;
    flex-shrink: 0;
    color: var(--color-text-muted);
    align-self: center;
  }
  /* The new value is the point of the card: it reads as the answer, not a diff cell. */
  .proposal-after {
    font-weight: 600;
    color: var(--color-text-primary);
    word-break: break-word;
  }

  .proposal-why {
    margin: 0;
    font-size: 0.8125rem;
    line-height: 1.5;
    color: var(--color-text-secondary);
  }
  .copilot-ideas,
  .copilot-caveats ul {
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .copilot-ideas {
    display: grid;
    gap: 0.35rem;
  }
  .copilot-ideas li {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.45rem 0.55rem;
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
    background: var(--color-bg-elevated);
  }
  .copilot-ideas strong {
    color: var(--color-text-primary);
    font-size: 0.75rem;
    line-height: 1.35;
  }
  .copilot-ideas span {
    flex: none;
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: 0.625rem;
  }
  .copilot-caveats {
    display: grid;
    gap: 0.35rem;
    padding: 0.55rem 0.65rem;
    border-left: 2px solid var(--color-warning);
    background: color-mix(in srgb, var(--color-warning) 7%, transparent);
    color: var(--color-text-secondary);
    font-size: 0.72rem;
    line-height: 1.45;
  }
  .copilot-caveats > strong {
    color: var(--color-text-primary);
    font-size: 0.6875rem;
  }
  .copilot-caveats li + li { margin-top: 0.2rem; }
  .copilot-caveats li::before { content: "- "; }
  .proposal-note {
    margin: 0;
    font-size: 0.75rem;
    line-height: 1.45;
    color: var(--color-text-secondary);
  }
  .proposal-note--applied {
    color: var(--color-success-text);
  }
  .proposal-note--warn {
    color: var(--color-warning-text);
  }

  .proposal-actions {
    display: flex;
    gap: var(--space-2);
  }
  /* Only the width deltas remain local — enough that the label swap to "Applying…"
     doesn't resize the button under the cursor. */
  .proposal-apply {
    min-width: 9.5rem;
  }
  /* Applying… is a STATUS, not an inert control — don't grey out the one line the
     user is waiting to read. */
  .proposal-apply.is-busy:disabled {
    opacity: 1;
    cursor: progress;
  }  .proposal-apply:focus-visible,
  .proposal-dismiss:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  @media (prefers-reduced-motion: reduce) {
    .proposal-apply,
    .proposal-dismiss { transition: none; }
    .proposal-apply:active:not(:disabled) { transform: none; }
  }

  /* ═══ Seed card — the user's OWN idea, priced like a purchase ═══
     Same grammar as a proposal (head → fields → why → actions) but never a diff
     table (free text has nothing to diff against), and its state is TERMINAL:
     once settled, the card never re-offers Evaluate/Dismiss again — see
     chatLedger.seedOutcome, derived from durable receipts, not local memory. */
  .seed-card {
    position: relative;
    display: grid;
    gap: var(--space-2);
    margin-top: var(--space-2);
    padding: var(--space-3) var(--space-3);
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border-emphasis);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
    overflow: hidden;
  }
  .seed-card--pending {
    background: color-mix(in srgb, var(--color-accent) 2%, var(--color-bg-elevated));
    border-color: color-mix(in srgb, var(--color-accent) 22%, var(--color-border));
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--color-accent) 4%, transparent);
  }
  .seed-card--pending::before {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    width: 28%;
    height: 2px;
    border-radius: 999px;
    background: var(--color-accent);
    transform: translateX(-105%);
    animation: seed-evaluation-progress 1.8s var(--chat-motion) infinite;
  }
  .seed-card--pending .seed-card-head {
    color: var(--color-accent-dark);
  }
  @keyframes seed-evaluation-progress {
    0% {
      transform: translateX(-105%);
    }
    60%,
    100% {
      transform: translateX(365%);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .seed-card--pending::before {
      width: 100%;
      opacity: 0.55;
      transform: none;
      animation: none;
    }
  }
  .seed-card--accepted {
    background: color-mix(in srgb, var(--color-success) 4%, var(--color-bg-elevated));
    border-color: color-mix(in srgb, var(--color-success) 24%, transparent);
    box-shadow: none;
  }
  .seed-card--demoted,
  .seed-card--failed {
    background: var(--color-bg-surface);
    border-color: var(--color-border);
    box-shadow: none;
  }
  .seed-card-head {
    display: flex;
    align-items: center;
    gap: var(--space-1-5);
  }
  .seed-card :global(.seed-card-icon) {
    width: 0.875rem;
    height: 0.875rem;
    flex-shrink: 0;
    color: var(--color-accent-dark);
  }
  .seed-card :global(.seed-card-icon--accepted) {
    color: var(--color-success-text);
  }
  .seed-card-title {
    font-family: var(--font-display);
    font-size: 0.8125rem;
    font-weight: 700;
    line-height: 1.35;
    color: var(--color-text-primary);
  }
  .seed-card--accepted .seed-card-title {
    color: var(--color-success-text);
  }
  .seed-card-fields {
    display: grid;
    gap: var(--space-2);
    margin: 0;
    padding: var(--space-2) var(--space-3);
    background: color-mix(in srgb, var(--color-bg-surface) 70%, transparent);
    border-radius: var(--radius-md);
  }
  .seed-card-why {
    margin: 0;
    font-size: 0.8125rem;
    line-height: 1.5;
    color: var(--color-text-secondary);
  }
  .seed-card-result {
    display: grid;
    gap: var(--space-1);
    padding-top: var(--space-2);
    border-top: 1px solid color-mix(in srgb, var(--color-border) 72%, transparent);
  }
  .seed-card-result-label {
    font-size: 0.6875rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }
  .seed-card-result strong {
    font-size: 0.875rem;
    color: var(--color-text-primary);
  }
  .seed-card-result p {
    margin: 0;
    font-size: 0.8125rem;
    line-height: 1.45;
    color: var(--color-text-secondary);
  }
  .seed-card-result-score {
    width: fit-content;
    padding: 0.125rem var(--space-1-5);
    border-radius: 999px;
    background: var(--color-bg-surface);
    font-size: 0.6875rem;
    font-weight: 600;
    color: var(--color-text-secondary);
  }
  .seed-card-result-link {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    width: fit-content;
    min-height: 2rem;
    margin-top: var(--space-1);
    font-size: 0.75rem;
    font-weight: 700;
    color: var(--color-accent-dark);
    text-underline-offset: 3px;
  }
  .seed-card-result-link :global(svg) {
    width: 0.75rem;
    height: 0.75rem;
  }
  .seed-card-cost {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    margin-left: var(--space-1);
  }
  .seed-card-cost :global(svg) {
    width: 0.7rem;
    height: 0.7rem;
  }
  .synthesis-evidence {
    padding-top: var(--space-1);
    border-top: 1px solid color-mix(in srgb, var(--color-border) 72%, transparent);
    font-size: 0.75rem;
    color: var(--color-text-secondary);
  }
  .synthesis-evidence summary {
    width: fit-content;
    cursor: pointer;
    font-weight: 700;
    color: var(--color-text-primary);
  }
  .synthesis-evidence ul {
    display: grid;
    gap: var(--space-1);
    margin: var(--space-2) 0 0;
    padding-left: 1.1rem;
    line-height: 1.45;
  }

  /* Evidence the analyst actually opened before answering — provenance receipts,
     not a "thinking" performance. Quiet: they are not the content. */
  .tool-receipts {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
    margin: 0 0 var(--space-2);
    padding: 0;
    list-style: none;
  }
  /* Provenance, on a surface fill — muted would be 4.4:1 here, under AA. */
  .tool-receipt {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    padding: var(--space-1) var(--space-2);
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-full, 9999px);
    font-family: var(--font-mono);
    font-size: 0.625rem;
    letter-spacing: 0.08em;
    color: var(--color-text-secondary);
  }
  .tool-receipt :global(.tool-receipt-icon) {
    width: 0.6875rem;
    height: 0.6875rem;
    flex-shrink: 0;
  }

  .entry-note {
    margin: 0;
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-style: italic;
    color: var(--color-text-muted);
  }
  .entry-pending-line {
    margin: 0;
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: var(--color-text-muted);
  }

  .chat-error {
    margin: 0;
    padding: var(--space-1-5) var(--space-3) 0;
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    color: var(--color-error-text);
  }
  .chat-retry {
    margin-left: var(--space-2);
    padding: var(--space-1) var(--space-1-5);
    background: transparent;
    border: 1px solid var(--color-input-border);
    border-radius: var(--radius-md);
    color: var(--color-text-primary);
    font-family: var(--font-body);
    font-size: 0.6875rem;
    font-weight: 700;
    cursor: pointer;
  }
  .chat-retry:hover {
    background: var(--color-bg-surface);
  }
  .chat-retry:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .chat-list:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: -2px;
  }
  .chat-note {
    margin: 0;
    padding: var(--space-1-5) var(--space-3) 0;
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }
  .chat-cap {
    margin: 0;
    padding: var(--space-1-5) var(--space-3) 0;
    font-size: 0.75rem;
    line-height: 1.45;
    color: var(--color-text-secondary);
  }

  /* Suggested questions — a quiet row on the composer's own tinted zone, so they
     read as part of the input affordance rather than a separate widget. */
  .chat-input {
    padding: var(--space-3);
    border-top: 1px solid var(--color-border);
    background: color-mix(in srgb, var(--chat-wash) 82%, transparent);
    /* Warm brown shadow tint to match the parchment identity above — derived
       from the same amber token as --chat-warm-tint (darkened, then 6% alpha)
       instead of a raw hex. */
    box-shadow: 0 -1rem 2.5rem
      color-mix(in srgb, color-mix(in srgb, var(--color-warning) 45%, black) 6%, transparent);
  }

  /* ═══ Follow-ups ═══
     A compact continuation of the analyst's last message. It lives inside the
     scrollable transcript and stays readable without becoming a second panel. */
  .followups {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    margin: var(--space-1) var(--space-4) var(--space-5);
    padding: var(--space-3) var(--space-1) 0;
    background: transparent;
    border: 0;
    border-top: 1px solid var(--color-border-emphasis);
    border-radius: 0;
  }
  .followups-title {
    margin: 0;
    padding: 0 0 var(--space-1-5);
    font-family: var(--font-body);
    font-size: 0.625rem;
    font-weight: 600;
    letter-spacing: 0.015em;
    color: var(--color-text-muted);
  }
  /* List-row treatment at full strength: these chips are the main way into the
     next question, so they get real hairlines and full-opacity secondary text —
     the old 86%-alpha text on a 4%-alpha border was the least visible
     affordance on the page. */
  .followup {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: var(--space-3);
    width: 100%;
    padding: 0.55rem 0;
    background: transparent;
    border: 0;
    border-top: 1px solid var(--color-border);
    border-radius: 0;
    color: var(--color-text-secondary);
    font-family: var(--font-body);
    font-size: 0.75rem;
    font-weight: 500;
    line-height: 1.35;
    text-align: left;
    cursor: pointer;
    transition: background 180ms var(--chat-motion), color 180ms var(--chat-motion),
      transform 180ms var(--chat-motion);
  }
  .followup:hover {
    background: transparent;
    color: var(--color-text-primary);
  }
  .followup:active {
    color: var(--color-accent-dark);
    transform: scale(0.995);
  }
  .followup:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: -2px;
    border-radius: var(--radius-md);
  }
  .followup :global(.followup-icon) {
    width: 0.75rem;
    height: 0.75rem;
    flex-shrink: 0;
    color: var(--color-text-muted);
    transition: color 180ms var(--chat-motion), transform 180ms var(--chat-motion);
  }
  .followup:hover :global(.followup-icon) {
    color: var(--color-accent);
    transform: translateX(0.125rem);
  }

  /* Compact window: the whole panel steps down a notch — follow-ups, composer,
     proposal cards. A companion window is read at arm's length beside the table,
     not leaned into. */
  .chat-thread--rail .proposal,
  .chat-thread--rail .receipt {
    padding: var(--space-3) var(--space-3);
    gap: var(--space-2);
  }
  .chat-thread--rail .proposal-title,
  .chat-thread--rail .receipt-title {
    font-size: 0.75rem;
  }
  .chat-thread--rail .proposal-why,
  .chat-thread--rail .receipt-note {
    font-size: 0.75rem;
  }
  .chat-thread--rail .proposal-field dd,
  .chat-thread--rail .receipt-field dd {
    font-size: 0.6875rem;
  }
  /* Apply mutates workspace state — it keeps the full .ledger-btn footer scale
     (12px/700, 2.25rem, min-width above) even in the compact rail, where the old
     11px shrink left it SMALLER than the free-form cancels around it. */
  .chat-thread--rail :global(.composer textarea) {
    font-size: 0.75rem;
  }

  /* Full-size: preserve the compact message treatment with a wider reading measure. */
  .chat-thread--focus .followups {
    width: min(42rem, 100%);
    margin-top: var(--space-2);
    margin-bottom: var(--space-6);
    padding: var(--space-3) 0 0;
  }
  .chat-thread--focus .followups-title {
    font-size: 0.6875rem;
  }
  .chat-thread--focus .followup {
    font-size: 0.75rem;
    line-height: 1.4;
  }

  @media (prefers-reduced-motion: reduce) {
    .followup {
      transition: none;
      transform: none;
    }
    .chat-operation::after,
    .chat-operation-pulse::after {
      animation: none;
    }
  }

  @media (max-width: 420px) {
    .chat-head {
      gap: var(--space-2);
      padding-left: var(--space-3);
    }
    .chat-subtitle,
    .chat-head-count-noun {
      display: none;
    }
    .chat-head-actions {
      margin-left: 0;
    }
    .chat-thread--main .entry,
    .chat-thread--main .chat-status,
    .chat-thread--main .chat-input,
    .chat-thread--main .chat-error,
    .chat-thread--main .chat-status--locked,
    .chat-thread--main .chat-operation {
      padding-left: var(--space-3);
      padding-right: var(--space-3);
    }
    .chat-thread--main .entry-user .entry-body {
      max-width: 92%;
    }
    .proposal-actions {
      display: grid;
      grid-template-columns: minmax(0, 1fr);
    }
    .proposal-actions :global(.ledger-btn) {
      justify-content: center;
      width: 100%;
    }
    .proposal-apply {
      min-width: 0;
    }
  }

  /* Rail dock: the panel is CONTENT-height; the parent (SelectionWorkbench
     shell) owns placement — beside the workbench it makes the rail sticky and
     caps it to the viewport, below 1280px it stacks as a normal block. Never
     force height:100% here: the grid area matches the tall candidate column
     and the panel would render a void below its input. Under the parent's
     max-height cap, the message list is the only child that shrinks (and
     scrolls); the head and input keep their size. */
  .chat-thread--rail .chat-head,
  .chat-thread--rail .chat-head-copy,
  .chat-thread--rail .chat-jump-row,
  .chat-thread--rail .chat-input {
    flex-shrink: 0;
  }
  .chat-thread--rail .chat-list {
    flex: 1 1 auto;
  }
</style>
