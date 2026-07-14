<script lang="ts">
  // The continuous analyst ledger (continuous-analyst-ledger plan, Phase 1):
  // ONE per-job thread, segmented by checkpoint. Past segments collapse to
  // read-only disclosure rows; the active checkpoint is the only expanded,
  // writable segment; pipeline runs appear as SYSTEM activity — live while
  // running (job SSE), frozen into boundary markers afterwards. The composer
  // never disappears: it yields to a working-status footer while stages run
  // and to a closed-transcript footer once the run is terminal.
  //
  // Segment chrome renders ONLY when there is history beyond the active
  // segment — a first arrival at G1 looks exactly like the plain conversation.
  import { ChevronDown, Loader2 } from "lucide-svelte";
  import { SvelteSet } from "svelte/reactivity";
  import type { IdeaFocus, GateArtifact, GateG1PatchFields, GateG2PatchFields } from "$lib/api";
  import { chatLedger } from "$lib/stores/chatLedger.svelte";
  import ChatThread from "./ChatThread.svelte";
  import LedgerActivityRow from "./LedgerActivityRow.svelte";
  import Sheet from "$lib/components/ui/Sheet.svelte";

  /** 'history' = past segments + markers only, no footer — used above a surface
   *  that owns the ACTIVE conversation itself (GateWorkbench / SelectionWorkbench),
   *  so cross-checkpoint continuity shows without double-mounting a composer.
   *  Renders nothing at all when there is no history yet. */
  type InteractionState = "composing" | "working" | "readonly" | "history";

  interface Props {
    jobId: string;
    interactionState: InteractionState;
    /** The checkpoint the composer anchors to while composing (1=G1, 4=G2, 5=G3). */
    activeGateStage?: 1 | 4 | 5 | null;
    /** 'card' = own bordered panel (rail, run shell, transcript); 'flat' = embedded
     *  in a parent card that owns the chrome (GateWorkbench conversation zone). */
    chrome?: "card" | "flat";
    /** Narrow contexts (20rem rail, mobile): past segments open in a Sheet instead
     *  of expanding inline — inline expansion there shoves the composer off-screen. */
    expandInSheet?: boolean;
    /** Working-state live data (job SSE fields, passed straight from the job). */
    jobStatus?: string | null;
    currentStageName?: string | null;
    stagesCompleted?: number | null;
    totalStages?: number | null;
    progressPercent?: number | null;
    queuePosition?: number | null;
    /** Frozen boundary-marker text per CLOSED segment (client-synthesized in
     *  Phase 1, persisted rows later), keyed by gateStage. */
    boundaryMarkers?: Record<number, string>;
    // ── pass-through to the active ChatThread ──
    gateArtifact?: GateArtifact | null;
    applying?: boolean;
    applyCapReached?: boolean;
    currentIdeaFocus?: IdeaFocus;
    onApplyGatePatch?: (patch: GateG1PatchFields | GateG2PatchFields, messageId?: string) => void | Promise<void>;
    onApplyPatch?: (ideaFocus: IdeaFocus) => void | Promise<void>;
    onContinue?: () => void;
    continuing?: boolean;
    appliedPatchIds?: ReadonlySet<string>;
    /** Suggested questions for the ACTIVE segment — rendered inside the thread,
     *  above its composer. */
    starters?: string[];
    weakPool?: boolean;
  }

  let {
    jobId,
    interactionState,
    activeGateStage = null,
    chrome = "card",
    expandInSheet = false,
    jobStatus = null,
    currentStageName = null,
    stagesCompleted = null,
    totalStages = null,
    progressPercent = null,
    queuePosition = null,
    boundaryMarkers = {},
    gateArtifact = null,
    applying = false,
    applyCapReached = false,
    currentIdeaFocus = "auto",
    onApplyGatePatch,
    onApplyPatch,
    onContinue,
    continuing = false,
    appliedPatchIds,
    starters = [],
    weakPool = $bindable(false),
  }: Props = $props();

  const SEGMENT_LABEL: Record<number, string> = {
    1: "Niche checkpoint",
    4: "Audience checkpoint",
    5: "Idea selection",
  };

  let chatThreadRef: ChatThread | undefined = $state();

  // A retry that neither disables nor shows progress invites the impatient click —
  // and `chatLedger.reload()` has no in-flight guard, so each one raced the last.
  let retrying = $state(false);
  async function retry() {
    if (retrying) return;
    retrying = true;
    try {
      await chatLedger.reload();
    } finally {
      retrying = false;
    }
  }
  /** Forwarded so existing parents (GateWorkbench) keep their bind:this contract. */
  export function stopStreaming() {
    chatThreadRef?.stopStreaming();
  }
  export function appendReceipt(receipt: { rows: { label: string; value: string }[]; note: string }) {
    chatThreadRef?.appendReceipt(receipt);
  }

  $effect(() => {
    void chatLedger.init(jobId);
  });

  // Segments other than the actively-composed one — i.e. closed history. In
  // 'history' mode the active gate's conversation lives in the surface below
  // (GateWorkbench/SelectionWorkbench), so it's excluded here too.
  const pastSegments = $derived(
    chatLedger.segments.filter(
      (s) =>
        !((interactionState === "composing" || interactionState === "history") && s.gateStage === activeGateStage) &&
        // Only conversational/receipt rows make a segment worth showing.
        s.messages.some((m) => m.role === "user" || m.role === "assistant" || m.role === "receipt"),
    ),
  );
  const showSegmentChrome = $derived(pastSegments.length > 0);
  // History-only mode with nothing to show renders nothing — no empty panel.
  const renderNothing = $derived(
    interactionState === "history" && pastSegments.length === 0 && !chatLedger.loadFailed,
  );

  function segmentMeta(gateStage: number): string {
    const msgs = chatLedger.segmentMessages(gateStage);
    const turns = msgs.filter((m) => m.role === "user" || m.role === "assistant").length;
    const changes = msgs.filter((m) => m.role === "receipt").length;
    const parts = [`${turns} message${turns === 1 ? "" : "s"}`];
    if (changes > 0) parts.push(`${changes} change${changes === 1 ? "" : "s"} applied`);
    return parts.join(" · ");
  }
  function segmentChanges(gateStage: number): number {
    return chatLedger.segmentMessages(gateStage).filter((m) => m.role === "receipt").length;
  }

  // ── Expansion state: inline (gate/transcript contexts) or Sheet (rail/mobile). ──
  let expandedStages = $state(new SvelteSet<number>());
  let sheetStage = $state<number | null>(null);
  function toggleSegment(gateStage: number) {
    if (expandInSheet) {
      sheetStage = gateStage;
      return;
    }
    if (expandedStages.has(gateStage)) expandedStages.delete(gateStage);
    else expandedStages.add(gateStage);
  }

  // ── Live-activity staleness guard: a frozen precise percent reads as stuck. ──
  let lastProgressAt = $state(Date.now());
  let now = $state(Date.now());
  $effect(() => {
    // Any live-progress field changing re-stamps freshness.
    void progressPercent;
    void stagesCompleted;
    void currentStageName;
    lastProgressAt = Date.now();
  });
  $effect(() => {
    if (interactionState !== "working") return;
    const t = setInterval(() => {
      now = Date.now();
    }, 5000);
    return () => clearInterval(t);
  });
  const progressStale = $derived(interactionState === "working" && now - lastProgressAt > 45_000);

  const isQueuedish = $derived(jobStatus === "QUEUED" || jobStatus === "PENDING");
  const liveText = $derived.by(() => {
    if (progressStale) return "Still working… (reconnecting)";
    if (isQueuedish) return `In queue${queuePosition ? ` · position ${queuePosition}` : ""}`;
    const stageBit =
      stagesCompleted != null && totalStages ? `stage ${stagesCompleted} of ${totalStages}` : "working";
    const phase = jobStatus === "RUNNING_PHASE2" ? "Deep research" : jobStatus === "REGENERATING" ? "New ideas" : "Discovery";
    return currentStageName ? `${phase} · ${currentStageName} · ${stageBit}` : `${phase} · ${stageBit}`;
  });

  const workingHeadline = $derived.by(() => {
    switch (jobStatus) {
      case "REGENERATING":
        return "NEW IDEAS GENERATING";
      case "RUNNING_PHASE2":
        return "REPORT GENERATING";
      default:
        return "ANALYST OPENS AT THE NEXT CHECKPOINT";
    }
  });
  const workingLine = $derived.by(() => {
    const stageBit =
      stagesCompleted != null && totalStages ? `stage ${stagesCompleted} of ${totalStages}` : "the next stage";
    switch (jobStatus) {
      case "QUEUED":
      case "PENDING":
        return `In queue${queuePosition ? ` · position ${queuePosition}` : ""}`;
      case "REGENERATING":
        return `Working on ${stageBit} — the analyst returns when they're ready.`;
      case "RUNNING_PHASE2":
        return `Working on ${stageBit}. This is the final leg — your report opens when it's done.`;
      default:
        return `Working on ${stageBit}`;
    }
  });
</script>

{#if !renderNothing}
<section class="ledger ledger--{chrome}" aria-label="Research ledger">
  {#if showSegmentChrome || interactionState !== "composing"}
    <header class="ledger-head">
      <span class="ledger-tag">Research ledger</span>
      {#if chatLedger.historyLoaded && !chatLedger.loadFailed}
        <span
          class="ledger-count"
          title="Questions this run — {chatLedger.usedTurns} of {chatLedger.maxTurns} used"
          aria-label="Questions this run — {chatLedger.usedTurns} of {chatLedger.maxTurns} used"
        >{chatLedger.usedTurns}<span class="ledger-count-max">/{chatLedger.maxTurns}</span></span>
      {/if}
    </header>
  {/if}

  {#if chatLedger.loadFailed}
    <div class="ledger-load-error" role="alert">
      <span>Earlier conversation didn't load.</span>
      <button type="button" class="ledger-retry" disabled={retrying} onclick={retry}>
        {#if retrying}
          <Loader2 class="w-3 h-3 animate-spin" aria-hidden="true" />
          Retrying&hellip;
        {:else}
          Retry
        {/if}
      </button>
    </div>
  {/if}

  {#each pastSegments as seg (seg.gateStage)}
    {@const expanded = expandedStages.has(seg.gateStage)}
    <button
      type="button"
      class="segment-row"
      aria-haspopup={expandInSheet ? "dialog" : undefined}
      aria-expanded={expandInSheet ? undefined : expanded}
      aria-controls={expandInSheet ? undefined : `segment-panel-${seg.gateStage}`}
      onclick={() => toggleSegment(seg.gateStage)}
    >
      <span class="ledger-check segment-check" aria-hidden="true">&#10003;</span>
      <span class="segment-name">{SEGMENT_LABEL[seg.gateStage] ?? `Checkpoint ${seg.gateStage}`}</span>
      <span class="segment-meta" class:has-changes={segmentChanges(seg.gateStage) > 0}>&middot; {segmentMeta(seg.gateStage)}</span>
      <ChevronDown
        class="segment-chevron {(expandInSheet ? sheetStage === seg.gateStage : expanded) ? 'is-open' : ''}"
        aria-hidden="true"
      />
    </button>
    {#if !expandInSheet}
      <div id="segment-panel-{seg.gateStage}" class="segment-expand" class:is-open={expanded}>
        <div class="segment-expand-inner">
          {#if expanded}
            <ChatThread {jobId} dock="main" gateStage={seg.gateStage} readOnly showHistoryRetry={false} {currentIdeaFocus} {gateArtifact} />
            <p class="segment-closed-note"><span class="ledger-check segment-check" aria-hidden="true">&#10003;</span> Checkpoint passed</p>
          {/if}
        </div>
      </div>
    {/if}
    {#if boundaryMarkers[seg.gateStage]}
      <LedgerActivityRow text={boundaryMarkers[seg.gateStage]} />
    {/if}
  {/each}

  {#if interactionState === "composing" && activeGateStage}
    {#if showSegmentChrome}
      <div class="segment-active-head">
        <span class="segment-active-pill">{SEGMENT_LABEL[activeGateStage]}</span>
      </div>
    {/if}
    <ChatThread
      bind:this={chatThreadRef}
      showHistoryRetry={false}
      {jobId}
      dock="main"
      gateStage={activeGateStage}
      {gateArtifact}
      {applying}
      {applyCapReached}
      {currentIdeaFocus}
      {onApplyGatePatch}
      {onApplyPatch}
      {onContinue}
      {continuing}
      appliedPatchIds={appliedPatchIds ?? chatLedger.appliedPatchIds}
      {starters}
      bind:weakPool
    />
  {:else if interactionState === "working"}
    <LedgerActivityRow live text={liveText} percent={isQueuedish ? null : progressPercent} stale={progressStale} />
    <footer class="ledger-working">
      <span class="ledger-working-headline">{workingHeadline}</span>
      <span class="ledger-working-line">
        {workingLine}<span class="ledger-caret" aria-hidden="true"></span>
      </span>
    </footer>
  {:else if interactionState === "readonly"}
    <footer class="ledger-closed">
      {chatLedger.usedTurns}/{chatLedger.maxTurns} questions used &middot; conversation closed
    </footer>
  {/if}
</section>
{/if}

{#if expandInSheet}
  <Sheet
    open={sheetStage !== null}
    title={sheetStage !== null ? (SEGMENT_LABEL[sheetStage] ?? "Checkpoint") : ""}
    onClose={() => (sheetStage = null)}
  >
    {#if sheetStage !== null}
      <ChatThread {jobId} dock="main" gateStage={sheetStage} readOnly {currentIdeaFocus} {gateArtifact} />
      <p class="segment-closed-note"><span class="ledger-check segment-check" aria-hidden="true">&#10003;</span> Checkpoint passed</p>
    {/if}
  </Sheet>
{/if}

<style>
  .ledger {
    --ledger-motion: cubic-bezier(0.32, 0.72, 0, 1);
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: hidden;
  }
  .ledger--card {
    background: var(--color-bg-elevated);
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 52%, transparent);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
  }

  .ledger-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
    padding: var(--space-3) var(--space-3) var(--space-2);
  }
  .ledger-tag {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--color-text-muted);
  }
  .ledger-count {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    color: var(--color-text-secondary);
  }
  .ledger-count-max {
    color: var(--color-text-muted);
  }

  .ledger-load-error {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3);
    border-top: 1px solid var(--color-border);
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    color: var(--color-text-secondary);
  }
  .ledger-retry {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    min-height: 1.75rem;
    min-width: 5.25rem;
    justify-content: center;
    padding: var(--space-1) var(--space-2);
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-input-border);
    border-radius: var(--radius-md);
    color: var(--color-text-secondary);
    font-family: var(--font-body);
    font-size: 0.6875rem;
    font-weight: 700;
    cursor: pointer;
    transition: border-color 150ms var(--ledger-motion), color 150ms var(--ledger-motion);
  }
  .ledger-retry:hover {
    border-color: var(--color-border-emphasis);
    color: var(--color-text-primary);
  }
  .ledger-retry:active:not(:disabled) {
    background: var(--color-bg-hover);
  }
  .ledger-retry:disabled {
    opacity: 0.6;
    cursor: progress;
  }
  .ledger-retry:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  /* ── Collapsed past segment — filing-cabinet register: all mono, all muted,
     one green outcome mark. One register quieter than live entries. ── */
  .segment-row {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    width: 100%;
    min-height: 2.25rem;
    padding: var(--space-2) var(--space-3);
    background: transparent;
    border: 0;
    border-top: 1px solid var(--color-border);
    text-align: left;
    cursor: pointer;
    transition: background 150ms var(--ledger-motion);
  }
  .segment-row:hover {
    background: var(--color-bg-surface);
  }
  .segment-row:hover .segment-name,
  .segment-row:hover .segment-meta {
    color: var(--color-text-secondary);
  }
  .segment-row:active {
    background: var(--color-bg-hover);
  }
  .segment-row:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: -2px;
  }
  .segment-check {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    flex-shrink: 0;
  }
  /* This is the only CONTROL in the collapsed ledger — it must not look like the
     static eyebrow above it or the dead footer below it. Body face, readable size. */
  .segment-name {
    font-family: var(--font-body);
    font-size: 0.8125rem;
    font-weight: 600;
    letter-spacing: 0;
    text-transform: none;
    color: var(--color-text-secondary);
    white-space: nowrap;
  }
  .segment-row:hover .segment-name {
    color: var(--color-text-primary);
  }
  .segment-meta {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 500;
    font-variant-numeric: tabular-nums;
    color: var(--color-text-muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
  }
  .segment-meta.has-changes {
    color: var(--color-success-text);
  }
  .segment-row :global(.segment-chevron) {
    width: 0.875rem;
    height: 0.875rem;
    margin-left: auto;
    flex-shrink: 0;
    color: var(--color-text-muted);
    transition: transform 200ms ease-in-out;
  }
  .segment-row :global(.segment-chevron.is-open) {
    transform: rotate(180deg);
  }

  /* Inline expansion — the app's canonical grid-rows collapse (Section.svelte). */
  .segment-expand {
    display: grid;
    grid-template-rows: 0fr;
    transition: grid-template-rows 220ms ease-out;
  }
  .segment-expand.is-open {
    grid-template-rows: 1fr;
  }
  .segment-expand-inner {
    overflow: hidden;
    min-height: 0;
  }
  .segment-closed-note {
    margin: 0;
    padding: var(--space-2) var(--space-3) var(--space-3);
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 500;
    color: var(--color-text-muted);
  }

  /* ── Active segment header — THE one accent element in the ledger. ── */
  .segment-active-head {
    padding: var(--space-2) var(--space-3) var(--space-1);
    border-top: 1px solid var(--color-border);
  }
  .segment-active-pill {
    display: inline-block;
    padding: var(--space-1) var(--space-2);
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-accent-dark);
    background: var(--color-accent-subtle);
    border: 1px solid color-mix(in srgb, var(--color-accent) 30%, transparent);
    border-radius: 9999px;
  }

  /* ── Working-status footer — replaces the composer zone entirely: the ledger's
     own pending vocabulary (mono lines + block-caret), nothing control-shaped. ── */
  .ledger-working {
    display: grid;
    gap: var(--space-1);
    min-height: 3.3rem;
    padding: var(--space-3) var(--space-3);
    border-top: 1px solid var(--color-border);
    background: color-mix(in srgb, var(--color-bg-surface) 60%, transparent);
  }
  .ledger-working-headline {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }
  .ledger-working-line {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    font-weight: 500;
    font-variant-numeric: tabular-nums;
    color: var(--color-text-secondary);
  }

  .ledger-closed {
    padding: var(--space-2) var(--space-3);
    border-top: 1px solid var(--color-border);
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 500;
    font-variant-numeric: tabular-nums;
    color: var(--color-text-muted);
  }

  @media (prefers-reduced-motion: reduce) {
    .segment-row,
    .ledger-retry {
      transition: none;
    }
    .segment-row :global(.segment-chevron) {
      transition: none;
    }
    .segment-expand {
      transition: none;
    }
  }
</style>
