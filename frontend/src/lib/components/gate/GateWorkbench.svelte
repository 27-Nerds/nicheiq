<script lang="ts">
  // Guided-research checkpoint ledger — Phase B (plans/eager-meandering-feather.md),
  // reshaped 2026-07 into ONE panel: gate header → framing document → conversation
  // (ChatThread, main dock, flat) → action bar with the single "Continue research"
  // CTA. Renders when a chatMode job is AWAITING_GATE; (gateStage) switches between
  // the G1 (niche validation) and G2 (audience + pain scope) framing documents.
  //
  // Apply feedback loop: applying a patch (chat-proposed OR the inline exclude-pain
  // chips — SAME apply_stay path) appends an APPLIED receipt into the conversation
  // right where the user acted, re-stamps the framing's revision meta, and marks the
  // changed fields with "Updated" tags. Change-confirmed = success green; orange
  // stays reserved for the gate badge and the Continue CTA.
  import { ArrowRight, Loader2 } from "lucide-svelte";
  import { SvelteSet } from "svelte/reactivity";
  import { gateAction, ApiError } from "$lib/api";
  import type { GateArtifact, GateG1Artifact, GateG2Artifact, GateG1PatchFields, GateG2PatchFields } from "$lib/api";
  import ChatThread from "$lib/components/chat/ChatThread.svelte";
  import { GATE_FIELD_LABEL, formatGateFieldValue } from "./gateFields";
  import { chatLedger } from "$lib/stores/chatLedger.svelte";
  import { gateSuggestions } from "$lib/components/chat/suggestions";

  interface Props {
    jobId: string;
    gateStage: 1 | 4;
    gateArtifact: GateArtifact | null;
    gateApplyCount: number;
    gateReachedAt: string | null;
    /** Live job status from SSE, used to distinguish request, queue, and worker
     * execution while an apply-and-stay round-trip is in flight. */
    jobStatus?: string | null;
    /** Guided-mode per-checkpoint segment prices (backend `GET /api/billing/stage-costs`'s
     *  `guided` object). Null until the layout's stage-costs fetch resolves, or on a
     *  backend that hasn't been redeployed with the field yet — Continue then renders
     *  without a price. */
    guidedCosts?: { s1: number; s2_4: number; s5: number; total: number } | null;
    /** Optimistic hook — mirrors the existing `onRegenerateStart` idiom. Called right
     *  after gate-action('continue') succeeds; the job page flips clientJob to QUEUED
     *  so the full research-progress screen takes over (this is a real resume, not a
     *  quick refresh). */
    onContinueStart?: () => void;
    /** Fired optimistically right before the apply_stay request goes out; the job
     *  page must keep rendering GateWorkbench through the QUEUED/RUNNING round-trip
     *  instead of switching to the progress screen — apply_stay always re-arrives at
     *  the SAME gate with a refreshed artifact. Paired with `onApplyStayError` below:
     *  every `onApplyStayStart` MUST be matched by either a gate re-arrival (handled
     *  by the job page's own AWAITING_GATE effect) or an `onApplyStayError` call, or
     *  the parent's "keep GateWorkbench mounted" override is stuck true forever. */
    onApplyStayStart?: () => void;
    /** Fired when the apply_stay request itself fails (cap 409, concurrency
     *  conflict, compensation, network) — i.e. every path where `applyPatch`'s
     *  catch block runs. The job page must drop its optimistic override here too,
     *  since a failed apply never produces the AWAITING_GATE re-arrival that would
     *  otherwise clear it, which would leave a later successful Continue stuck
     *  rendering GateWorkbench instead of handing off to the progress screen. */
    onApplyStayError?: () => void;
  }

  let {
    jobId,
    gateStage,
    gateArtifact,
    gateApplyCount,
    gateReachedAt,
    jobStatus = null,
    guidedCosts = null,
    onContinueStart,
    onApplyStayStart,
    onApplyStayError,
  }: Props = $props();

  const applyCapReached = $derived(gateApplyCount >= 5);
  const g1 = $derived(gateStage === 1 ? (gateArtifact as GateG1Artifact | null) : null);
  const g2 = $derived(gateStage === 4 ? (gateArtifact as GateG2Artifact | null) : null);

  // Handle on the embedded ChatThread — lets a gate action (continue/apply_stay)
  // cancel an in-flight chat stream first, so ChatThread's own local `messages`
  // state can't mutate after the job has already moved past this gate.
  let chatThreadRef: ChatThread | undefined = $state();

  // ── Continue research ──
  //
  // Continue is a PURCHASE now, not a free click. It buys the next segment of the pipeline:
  // at G1, stages 2-4 (audience + pain analysis); at G2, stage 5 (idea generation). That is what
  // makes this checkpoint mean something — previously the whole discovery phase was charged at
  // job creation and Continue cost nothing, so the gate could not gate spend at all.
  //
  // The price shown here is the price charged: the request carries it, and the server refuses
  // (409) rather than charging a different number if an admin re-priced the segment while this
  // gate was open.
  let continuing = $state(false);
  let continueError = $state("");
  /** Set when the user can't afford the next segment. They're standing right here when it
   *  happens — which is the point of charging at the checkpoint instead of letting the run die
   *  unattended three stages later. */
  let needsCredits = $state<{ balance: number; required: number } | null>(null);

  const continueCost = $derived(
    gateStage === 1 ? (guidedCosts?.s2_4 ?? null) : (guidedCosts?.s5 ?? null),
  );
  const buysLabel = $derived(
    gateStage === 1 ? "audience and pain analysis" : "idea generation",
  );

  async function handleContinue() {
    if (continuing) return;
    continuing = true;
    continueError = "";
    needsCredits = null;
    chatThreadRef?.stopStreaming();
    try {
      await gateAction(jobId, {
        action: "continue",
        gateStage,
        ...(continueCost != null ? { expectedCost: continueCost } : {}),
      });
      onContinueStart?.();
    } catch (e) {
      continuing = false;
      if (e instanceof ApiError && e.status === 402) {
        const body = e.details as { balance?: number; required?: number } | undefined;
        needsCredits = { balance: body?.balance ?? 0, required: body?.required ?? 0 };
        return;
      }
      continueError = e instanceof ApiError ? e.message : "Failed to continue research";
    }
  }

  // ── Apply-stay: the ONE apply path shared by chat-proposed patches (via
  //    ChatThread's onApplyGatePatch) and the inline exclude-pain chips below. ──
  let applying = $state(false);
  let applyQueued = $state(false);
  let applySnapshotReachedAt = $state<string | null>(null);
  let applyError = $state("");
  const applyActivity = $derived.by(() => {
    if (!applying) return null;
    if (jobStatus === "RUNNING" || jobStatus === "RUNNING_PHASE2") {
      return {
        title: "Worker is rebuilding this checkpoint",
        detail: "The analyst is re-deriving the framing with your change. You can leave this page open.",
      };
    }
    if (applyQueued || jobStatus === "QUEUED" || jobStatus === "PENDING") {
      return {
        title: "Change queued for a worker",
        detail: "Your change is saved. The checkpoint will refresh automatically when a worker picks it up.",
      };
    }
    return {
      title: "Submitting your change",
      detail: "Waiting for the research queue to confirm the update.",
    };
  });
  const blockedTitle = $derived(
    continuing ? "Starting the next research stage" : applyActivity?.title ?? "Research is active",
  );
  const blockedDetail = $derived(
    continuing
      ? "Waiting for the worker queue to confirm. Live stage progress will replace this checkpoint."
      : applyActivity?.detail ?? "The analyst will unlock when the update finishes.",
  );

  // Patch keys → framing-document field keys, so a completed apply can mark the
  // exact fields it changed (excluded_segments/segment_emphasis both land on the
  // segments subsection; pain_scope lands on the pains subsection).
  const PATCH_TO_FORM_FIELD: Record<string, string> = {
    niche_description: "niche_description",
    market_segments: "market_segments",
    industry_boundaries: "industry_boundaries",
    user_target_audience: "target_audience",
    primary_target_segment: "primary_target",
    excluded_segments: "segments",
    segment_emphasis: "segments",
    pain_scope: "pains",
  };

  // In-flight apply context: the patch being applied (for the receipt) and the
  // proposing chat message id (so its card flips to "Applied" on completion).
  let pendingPatch = $state<GateG1PatchFields | GateG2PatchFields | null>(null);
  let pendingApplyMessageId = $state<string | null>(null);
  // Framing fields changed by the LAST completed apply — rendered as "Updated"
  // tags until the next apply replaces them (or Continue moves the run forward).
  let lastChangedFields = $state(new SvelteSet<string>());
  // Chat message ids whose proposal was applied this session (terminal card state).
  // Union'd with the store's server-derived set (durable receipts carry the proposing
  // message id), so a reload no longer re-offers Apply on an already-applied patch.
  let appliedIds = $state(new SvelteSet<string>());
  const allAppliedIds = $derived(new Set([...appliedIds, ...chatLedger.appliedPatchIds]));

  const fieldUpdated = (key: string) => lastChangedFields.has(key);
  const revision = $derived(gateApplyCount + 1);

  $effect(() => {
    // A fresh (non-null, changed) gateReachedAt means the SAME gate re-arrived with
    // a refreshed artifact — the round-trip this "apply_stay" kicked off is done.
    if (applying && gateReachedAt && gateReachedAt !== applySnapshotReachedAt) {
      applying = false;
      applyQueued = false;
      applySnapshotReachedAt = null;
      excludedPainTitles = new SvelteSet();
      if (pendingPatch) {
        const patchEntries = Object.entries(pendingPatch);
        lastChangedFields = new SvelteSet(patchEntries.map(([f]) => PATCH_TO_FORM_FIELD[f] ?? f));
        if (pendingApplyMessageId) appliedIds.add(pendingApplyMessageId);
        chatThreadRef?.appendReceipt({
          rows: patchEntries.map(([field, value]) => ({
            label: GATE_FIELD_LABEL[field] ?? field,
            value: formatGateFieldValue(field, value),
          })),
          note: `Framing re-derived — revision ${gateApplyCount + 1}. Updated fields are marked above.`,
        });
        // The optimistic receipt above is the instant feedback; the backend wrote a
        // durable one when this same gate re-arrived. Reconcile so the row survives a
        // reload (the store swaps the local twin for the persisted one).
        void chatLedger.reload();
      }
      pendingPatch = null;
      pendingApplyMessageId = null;
    }
  });

  async function applyPatch(patch: GateG1PatchFields | GateG2PatchFields, messageId?: string) {
    if (applying || applyCapReached) return;
    applying = true;
    applyQueued = false;
    applySnapshotReachedAt = gateReachedAt;
    applyError = "";
    lastChangedFields = new SvelteSet();
    pendingPatch = patch;
    pendingApplyMessageId = messageId ?? null;
    chatThreadRef?.stopStreaming();
    try {
      onApplyStayStart?.();
      // sourceMessageId lets the backend's durable receipt point back at the proposing
      // chat message, so its card renders "Applied" even after a reload. Local ids
      // (optimistic, never persisted) would dangle — send only server-issued ones.
      const sourceMessageId = messageId && !messageId.startsWith("local-") ? messageId : undefined;
      await gateAction(jobId, { action: "apply_stay", gateStage, patch, sourceMessageId });
      // The API only returns after the atomic QUEUED flip and Redis enqueue both
      // succeed, so this is a truthful queue confirmation even if SSE is delayed.
      if (applying) applyQueued = true;
    } catch (e) {
      applying = false;
      applyQueued = false;
      applySnapshotReachedAt = null;
      pendingPatch = null;
      pendingApplyMessageId = null;
      applyError = e instanceof ApiError ? e.message : "Failed to apply changes";
      onApplyStayError?.();
    }
  }

  // ── Inline exclude-pain chips (G2 only) — compile into a pain_scope patch and
  //    apply through the exact same path a chat-proposed patch would use. ──
  let excludedPainTitles = $state(new SvelteSet<string>());
  function togglePainExcluded(title: string) {
    if (applying) return;
    if (excludedPainTitles.has(title)) excludedPainTitles.delete(title);
    else excludedPainTitles.add(title);
  }
  const hasPendingExclusions = $derived(excludedPainTitles.size > 0);
  function applyPainExclusions() {
    void applyPatch({ pain_scope: { excluded_titles: [...excludedPainTitles], pinned_titles: [] } });
  }
  function clearPainExclusions() {
    excludedPainTitles = new SvelteSet();
  }

  // ── Starter chips (static per gate — glue G2 in the plan) ──
  // Suggested questions track the checkpoint: they name THIS gate's real pains and
  // segments, react to a proposal sitting on the table, and steer to the exit once
  // the change budget is spent. Recomputed as the conversation and artifact change.
  const suggestions = $derived(
    gateSuggestions({
      gateStage,
      artifact: gateArtifact,
      messages: chatLedger.segmentMessages(gateStage),
      appliedPatchIds: allAppliedIds,
      applyCapReached,
      hasAppliedChange: gateApplyCount > 0,
    }),
  );

  function severityPct(v: number | null | undefined): number {
    return typeof v === "number" ? Math.round(v * 100) : 0;
  }
</script>

<section class="gate-card" aria-labelledby="gate-card-title">
  <div class="gate-inner">
    <header class="gate-head">
      <span class="gate-tag">GATE {gateStage === 1 ? "01" : "02"}</span>
      <h2 class="gate-title" id="gate-card-title">
        {gateStage === 1 ? "Niche validated" : "Audience mapped"}
      </h2>
      <p class="gate-copy">
        Research is paused here. Review the framing, ask the analyst for changes, and continue when it looks right.
      </p>
    </header>

    <div class="gate-framing" class:is-applying={applying} aria-busy={applying}>
      <div class="framing-head">
        <span class="framing-label">{gateStage === 1 ? "Niche framing" : "Audience & pain scope"}</span>
        <span class="framing-rev" aria-live="polite">
          Rev {revision}
          {#if gateApplyCount > 0}
            <span class="framing-rev-meta">&middot; {gateApplyCount}/5 changes used</span>
          {/if}
        </span>
      </div>

      <div class="framing-fields">
        {#if gateStage === 1}
          <dl class="gate-field" class:is-updated={fieldUpdated("niche_description")}>
            <dt>Niche description {#if fieldUpdated("niche_description")}<span class="field-updated">Updated</span>{/if}</dt>
            <dd>{g1?.niche_description ?? "—"}</dd>
          </dl>
          <dl class="gate-field" class:is-updated={fieldUpdated("market_segments")}>
            <dt>Market segments {#if fieldUpdated("market_segments")}<span class="field-updated">Updated</span>{/if}</dt>
            <dd>
              {#if g1?.market_segments?.length}
                <ul class="gate-chip-list">
                  {#each g1.market_segments as seg}
                    <li class="gate-chip">{seg}</li>
                  {/each}
                </ul>
              {:else}
                —
              {/if}
            </dd>
          </dl>
          <dl class="gate-field" class:is-updated={fieldUpdated("industry_boundaries")}>
            <dt>Industry boundaries {#if fieldUpdated("industry_boundaries")}<span class="field-updated">Updated</span>{/if}</dt>
            <dd>{g1?.industry_boundaries ?? "—"}</dd>
          </dl>
          <dl class="gate-field" class:is-updated={fieldUpdated("target_audience")}>
            <dt>Target audience {#if fieldUpdated("target_audience")}<span class="field-updated">Updated</span>{/if}</dt>
            <dd>
              {g1?.user_target_audience ?? "whole niche"}
              {#if g1?.audience_scope}
                <span class="gate-meta-tag">{g1.audience_scope.replace(/_/g, " ")}</span>
              {/if}
            </dd>
          </dl>
          {#if g1?.anchor_entities?.length}
            <details class="gate-expand">
              <summary>How we'll search</summary>
              <dl class="gate-field">
                <dt>Anchor terms</dt>
                <dd>
                  <ul class="gate-chip-list">
                    {#each g1.anchor_entities as term}
                      <li class="gate-chip">{term}</li>
                    {/each}
                  </ul>
                </dd>
              </dl>
              {#if g1?.disambiguation_exclusions?.length}
                <dl class="gate-field">
                  <dt>Excluded meanings</dt>
                  <dd>{g1.disambiguation_exclusions.join(", ")}</dd>
                </dl>
              {/if}
            </details>
          {/if}
        {:else if gateStage === 4}
          <dl class="gate-field" class:is-updated={fieldUpdated("primary_target")}>
            <dt>Primary segment {#if fieldUpdated("primary_target")}<span class="field-updated">Updated</span>{/if}</dt>
            <dd>{g2?.primary_target ?? "—"}</dd>
          </dl>

          <div class="gate-subsection" class:is-updated={fieldUpdated("segments")}>
            <h3 class="gate-subhead">
              Audience segments <span class="gate-count">{g2?.segments?.length ?? 0}</span>
              {#if fieldUpdated("segments")}<span class="field-updated">Updated</span>{/if}
            </h3>
            {#if g2?.segments?.length}
              <ul class="gate-segment-list">
                {#each g2.segments as seg}
                  <li class="gate-segment-row">
                    <span class="gate-segment-name">{seg.segment_name}</span>
                    <span class="gate-segment-meta">{seg.size_estimate ?? "n/a"} &middot; {seg.payability_class ?? "n/a"} payability</span>
                  </li>
                {/each}
              </ul>
            {:else}
              <p class="gate-empty-note">—</p>
            {/if}
          </div>

          <div class="gate-subsection" class:is-updated={fieldUpdated("pains")}>
            <h3 class="gate-subhead">
              Pain points <span class="gate-count">{g2?.pains?.length ?? 0}</span>
              {#if fieldUpdated("pains")}<span class="field-updated">Updated</span>{/if}
            </h3>
            {#if g2?.pains?.length}
              <ul class="gate-pain-list">
                {#each g2.pains as pain (pain.title)}
                  {@const excluded = excludedPainTitles.has(pain.title)}
                  <li class="gate-pain-row" class:is-excluded={excluded}>
                    <div class="gate-pain-main">
                      <span class="gate-pain-title">{pain.title}</span>
                      <div class="gate-pain-bar-track">
                        <div class="gate-pain-bar-fill" style:width="{severityPct(pain.severity)}%"></div>
                      </div>
                    </div>
                    <button
                      type="button"
                      class="gate-pain-toggle"
                      class:is-active={excluded}
                      aria-pressed={excluded}
                      disabled={applying}
                      onclick={() => togglePainExcluded(pain.title)}
                    >
                      {excluded ? "Excluded" : "Exclude"}
                    </button>
                  </li>
                {/each}
              </ul>
              {#if hasPendingExclusions}
                <div class="gate-pending-patch">
                  <span class="gate-pending-note">
                    {excludedPainTitles.size} pain{excludedPainTitles.size === 1 ? "" : "s"} excluded from ideation
                  </span>
                  <div class="gate-pending-actions">
                    <button type="button" class="gate-patch-apply" disabled={applying || applyCapReached} onclick={applyPainExclusions}>
                      {#if applying}<Loader2 class="w-3.5 h-3.5 animate-spin" aria-hidden="true" />{/if}
                      Apply changes
                    </button>
                    <button type="button" class="gate-patch-dismiss" disabled={applying} onclick={clearPainExclusions}>Keep as is</button>
                  </div>
                </div>
              {/if}
            {:else}
              <p class="gate-empty-note">—</p>
            {/if}
            {#if g2?.degraded === "pain_scope_only"}
              <p class="gate-degraded-note">Audience mapping didn't complete for this run — only pain scoping is available at this checkpoint.</p>
            {/if}
          </div>
        {/if}
      </div>

      {#if applyCapReached}
        <p class="gate-cap-note">Change limit reached for this checkpoint (5 max) — continue research to move forward.</p>
      {/if}
      {#if applyError}
        <p class="gate-error">{applyError}</p>
      {/if}
    </div>

    <!-- The active workflow conversation uses the same full reading presentation as
         the expanded analyst overlay. Only the host chrome differs. -->
    <ChatThread
      bind:this={chatThreadRef}
      {jobId}
      dock="rail"
      focused
      {gateStage}
      {gateArtifact}
      {applying}
      {applyCapReached}
      appliedPatchIds={allAppliedIds}
      blocked={applying || continuing}
      {blockedTitle}
      {blockedDetail}
      starters={continuing ? [] : suggestions}
      onApplyGatePatch={applyPatch}
    />

    <div class="gate-action-bar">
      <span class="gate-action-meta">{gateApplyCount}/5 changes used &middot; steering is free</span>
      <div class="gate-action-main">
        {#if needsCredits}
          <!-- The one moment where running out of credits is a fixable problem rather than a dead
               run: the user is here, the work hasn't started, and nothing has been charged. -->
          <p class="gate-topup" role="alert">
            This step needs {needsCredits.required}
            {needsCredits.required === 1 ? "credit" : "credits"} — you have {needsCredits.balance}.
            <a href="/billing">Top up</a> and continue; your checkpoint is saved.
          </p>
        {:else if continueError}
          <p class="gate-error">{continueError}</p>
        {:else if continueCost != null}
          <p class="gate-purchase">
            Runs the {buysLabel}. Costs {continueCost}
            {continueCost === 1 ? "credit" : "credits"}, and this checkpoint doesn't come back.
          </p>
        {/if}
        <button type="button" class="gate-continue-btn" disabled={continuing || applying} onclick={handleContinue}>
          {#if continuing}
            <span class="gate-worker-mark" aria-hidden="true"></span>
            Sending to worker&hellip;
          {:else}
            Continue research{continueCost != null ? ` · ${continueCost} ${continueCost === 1 ? "credit" : "credits"}` : ""}
            <span class="gate-continue-chip" aria-hidden="true">
              <ArrowRight class="w-3.5 h-3.5" />
            </span>
          {/if}
        </button>
      </div>
    </div>
  </div>
</section>

<style>
  /* Double-bezel (Phase C elevation polish, plan §"Elevation polish"): outer tray
     is a concentric frame around the inner card — bg-subtle + hairline ring +
     p-1.5 + radius-xl. Doubled vertical rhythm: this card's margin is 2x the
     design system's standard --space-6 section gap. The inner card is now a
     zoned ledger (head / framing / conversation / action bar) divided by
     hairlines — children carry their own padding. */
  .gate-card {
    --gate-motion: cubic-bezier(0.32, 0.72, 0, 1);
    margin: var(--space-12) 0;
    padding: var(--space-1-5);
    background: var(--color-bg-subtle);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-xl);
    animation: gate-card-in 240ms var(--gate-motion) both;
  }
  @keyframes gate-card-in {
    from { opacity: 0; clip-path: inset(0 0 8% 0); }
    to { opacity: 1; clip-path: inset(0 0 0 0); }
  }
  @media (prefers-reduced-motion: reduce) {
    .gate-card { animation: none; }
  }

  .gate-inner {
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
    overflow: hidden;
  }

  .gate-head {
    display: grid;
    gap: 0.3rem;
    padding: var(--space-5) var(--space-5) var(--space-4);
  }
  .gate-tag {
    justify-self: start;
    padding: 0.15rem 0.5rem;
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
  .gate-title {
    margin: 0;
    font-family: var(--font-display);
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--color-text-primary);
  }
  .gate-copy {
    margin: 0;
    font-size: 0.8125rem;
    line-height: 1.45;
    color: var(--color-text-muted);
  }

  /* ── Framing document zone — "the record under review" reads on the surface
     tint; conversation below stays on elevated white. ── */
  .gate-framing {
    display: grid;
    gap: 0.75rem;
    padding: var(--space-4) var(--space-5) var(--space-5);
    background: color-mix(in srgb, var(--color-bg-surface) 60%, transparent);
    border-top: 1px solid var(--color-border);
    transition: opacity 150ms var(--gate-motion);
  }
  .gate-framing.is-applying .framing-fields {
    opacity: 0.55;
  }
  .framing-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.5rem;
  }
  .framing-label {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }
  .framing-rev {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    color: var(--color-text-secondary);
  }
  .framing-rev-meta {
    font-weight: 500;
    color: var(--color-text-muted);
  }

  .framing-fields {
    display: grid;
    gap: 0.5rem;
    transition: opacity 150ms var(--gate-motion);
  }
  .gate-worker-mark {
    position: relative;
    flex-shrink: 0;
    width: 0.625rem;
    height: 0.625rem;
    border-radius: 50%;
    background: var(--color-accent);
  }
  .gate-worker-mark::after {
    content: "";
    position: absolute;
    inset: -0.3rem;
    border: 1px solid color-mix(in srgb, var(--color-accent) 40%, transparent);
    border-radius: inherit;
    animation: gate-operation-pulse 1.8s ease-out infinite;
  }
  @keyframes gate-operation-pulse {
    0% { opacity: 0.85; transform: scale(0.65); }
    75%, 100% { opacity: 0; transform: scale(1.35); }
  }
  /* Fields carry constant inner padding so the updated tint never shifts layout. */
  .gate-field {
    margin: 0;
    display: grid;
    gap: 0.2rem;
    padding: 0.45rem 0.5rem;
    border-radius: var(--radius-md);
  }
  .gate-field.is-updated,
  .gate-subsection.is-updated {
    background: color-mix(in srgb, var(--color-success) 7%, transparent);
  }
  .field-updated {
    margin-left: 0.35rem;
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 800;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-success-text);
  }
  .gate-field dt {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 800;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }
  .gate-field dd {
    margin: 0;
    font-size: 0.8125rem;
    line-height: 1.5;
    color: var(--color-text-primary);
    text-wrap: pretty;
  }
  .gate-chip-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    margin: 0.1rem 0 0;
    padding: 0;
    list-style: none;
  }
  .gate-chip {
    padding: 0.28rem 0.6rem;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: 9999px;
    font-size: 0.75rem;
    color: var(--color-text-secondary);
  }
  .gate-meta-tag {
    margin-left: 0.4rem;
    font-family: var(--font-mono);
    font-size: 0.625rem;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }
  .gate-expand {
    padding: 0.45rem 0.5rem 0;
    border-top: 1px solid var(--color-border);
    display: grid;
    gap: 0.5rem;
  }
  .gate-expand summary {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--color-text-secondary);
    cursor: pointer;
  }
  .gate-expand[open] summary {
    margin-bottom: 0.5rem;
  }

  .gate-subsection {
    display: grid;
    gap: 0.5rem;
    padding: 0.55rem 0.5rem 0.45rem;
    border-top: 1px solid var(--color-border);
    border-radius: var(--radius-md);
  }
  .gate-subhead {
    margin: 0;
    display: flex;
    align-items: baseline;
    gap: 0.4rem;
    font-size: 0.8125rem;
    font-weight: 700;
    color: var(--color-text-secondary);
  }
  .gate-count {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    color: var(--color-text-muted);
  }
  .gate-empty-note {
    margin: 0;
    font-size: 0.8125rem;
    color: var(--color-text-muted);
  }

  .gate-segment-list {
    display: grid;
    gap: 0.35rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .gate-segment-row {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.6rem;
    font-size: 0.8125rem;
  }
  .gate-segment-name {
    color: var(--color-text-primary);
    font-weight: 600;
  }
  .gate-segment-meta {
    color: var(--color-text-muted);
    font-size: 0.75rem;
    white-space: nowrap;
  }

  .gate-pain-list {
    display: grid;
    gap: 0.5rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .gate-pain-row {
    display: flex;
    align-items: center;
    gap: 0.7rem;
  }
  .gate-pain-row.is-excluded {
    opacity: 0.55;
  }
  .gate-pain-main {
    flex: 1;
    min-width: 0;
    display: grid;
    gap: 0.3rem;
  }
  .gate-pain-title {
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }
  .gate-pain-bar-track {
    height: 4px;
    background: var(--color-bg-elevated);
    border-radius: 9999px;
    overflow: hidden;
  }
  .gate-pain-bar-fill {
    height: 100%;
    background: var(--color-accent);
    border-radius: 9999px;
  }
  /* Pill toggle — same recipe as SelectionWorkbench's .regen-focus-btn (pill,
     transparent by default, filled/accent-outlined when active). Reimplemented
     locally: Svelte scopes component styles, so the class name can't be shared
     across components. */
  .gate-pain-toggle {
    flex-shrink: 0;
    min-height: 2rem;
    padding: 0.32rem 0.65rem;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
    color: var(--color-text-muted);
    font-family: var(--font-body);
    font-size: 0.75rem;
    font-weight: 700;
    cursor: pointer;
    transition: border-color 220ms var(--gate-motion), color 220ms var(--gate-motion), background 220ms var(--gate-motion);
  }
  .gate-pain-toggle:hover:not(:disabled) {
    color: var(--color-text-secondary);
    border-color: var(--color-border-emphasis);
  }
  .gate-pain-toggle.is-active {
    background: var(--color-accent-subtle);
    border-color: color-mix(in srgb, var(--color-accent) 30%, transparent);
    color: var(--color-accent-dark);
  }
  .gate-pain-toggle:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
  .gate-pain-toggle:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  /* Pending exclusions = the same object as a chat proposal: a staged change with a
     stated scope and two answers. Same card, same buttons, same words — the user
     shouldn't have to learn two grammars for one decision. */
  .gate-pending-patch {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 0.6rem;
    margin-top: 0.4rem;
    padding: 0.7rem 0.8rem;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border-emphasis);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
  }
  .gate-pending-note {
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }
  .gate-pending-actions {
    display: flex;
    gap: 0.45rem;
  }

  /* Apply / Keep-as-is — identical recipe to the chat proposal's buttons. */
  .gate-patch-apply {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    min-height: 2.25rem;
    padding: 0.45rem 0.9rem;
    background: var(--color-accent-hover);
    border: 1px solid var(--color-accent-hover);
    border-radius: var(--radius-md);
    color: var(--color-text-on-accent);
    font-family: var(--font-body);
    font-size: 0.75rem;
    font-weight: 700;
    cursor: pointer;
    transition: background 180ms var(--gate-motion), transform 180ms var(--gate-motion);
  }
  .gate-patch-apply:hover:not(:disabled) {
    background: var(--color-accent-dark);
  }
  .gate-patch-apply:active:not(:disabled) {
    transform: scale(0.98);
  }
  .gate-patch-apply:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
  .gate-patch-dismiss {
    min-height: 2.25rem;
    padding: 0.45rem 0.8rem;
    background: transparent;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    color: var(--color-text-secondary);
    font-family: var(--font-body);
    font-size: 0.75rem;
    font-weight: 700;
    cursor: pointer;
    transition: border-color 180ms var(--gate-motion), color 180ms var(--gate-motion);
  }
  .gate-patch-dismiss:hover:not(:disabled) {
    border-color: var(--color-border-emphasis);
    color: var(--color-text-primary);
  }
  .gate-patch-dismiss:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
  .gate-patch-apply:focus-visible,
  .gate-patch-dismiss:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .gate-degraded-note {
    margin: 0.2rem 0 0;
    font-size: 0.75rem;
    color: var(--color-text-muted);
  }

  .gate-cap-note {
    margin: 0;
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    color: var(--color-warning-text, var(--color-text-muted));
  }
  .gate-error {
    margin: 0;
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: var(--color-error);
  }

  /* ── Action bar — the checkpoint's exit. ONE focal action. ── */
  .gate-action-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 0.75rem;
    padding: var(--space-4) var(--space-5);
    border-top: 1px solid var(--color-border);
    background: color-mix(in srgb, var(--color-bg-surface) 60%, transparent);
  }
  .gate-action-meta {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-variant-numeric: tabular-nums;
    color: var(--color-text-muted);
  }
  /* Quiet purchase disclosure — states what the click buys, not a warning. Same
     muted/small register as .gate-action-meta. */
  .gate-purchase {
    margin: 0;
    max-width: 32rem;
    font-size: 0.75rem;
    line-height: 1.45;
    color: var(--color-text-muted);
  }
  /* Blocking state (can't afford the next segment) — warning token pattern, same
     recipe as .gate-cap-note's color but promoted to a full note with a fix-it link. */
  .gate-topup {
    margin: 0;
    max-width: 32rem;
    padding: 0.55rem 0.75rem;
    background: var(--color-warning-subtle);
    border: 1px solid var(--color-border-warning);
    border-radius: var(--radius-md);
    font-size: 0.75rem;
    line-height: 1.45;
    color: var(--color-warning-text);
  }
  .gate-topup a {
    color: var(--color-accent-dark);
    font-weight: 700;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .gate-topup a:hover {
    color: var(--color-accent);
  }
  .gate-action-main {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
    justify-content: flex-end;
  }
  .gate-continue-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.65rem;
    min-height: 2.75rem;
    padding: 0.65rem 0.5rem 0.65rem 1.15rem;
    background: var(--color-accent-hover);
    border: 1px solid var(--color-accent-hover);
    border-radius: 0.65rem;
    color: var(--color-text-on-accent);
    font-family: var(--font-body);
    font-size: 0.875rem;
    font-weight: 700;
    cursor: pointer;
    transition: background 220ms var(--gate-motion), transform 220ms var(--gate-motion);
  }
  .gate-continue-btn:hover:not(:disabled) {
    background: var(--color-accent-dark);
  }
  .gate-continue-btn:active:not(:disabled) {
    transform: scale(0.98);
  }
  .gate-continue-btn:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }
  .gate-continue-btn:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  /* Button-in-button nested arrow chip — no bare-icon precedent existed in
     DESIGN_SYSTEM.md's Buttons recipe, so this follows the app's existing pill
     chip idiom (radius-full, hairline-light fill) scaled down and nested inside
     the primary pill. Purely decorative: the button itself carries the label. */
  .gate-continue-chip {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    width: 1.75rem;
    height: 1.75rem;
    background: color-mix(in srgb, white 22%, transparent);
    border-radius: 9999px;
  }

  @media (prefers-reduced-motion: reduce) {
    .gate-framing,
    .framing-fields,
    .gate-pain-toggle,
    .gate-patch-apply,
    .gate-patch-dismiss,
    .gate-continue-btn {
      transition: none;
    }
    .gate-worker-mark::after {
      animation: none;
    }
    .gate-patch-apply:active:not(:disabled),
    .gate-continue-btn:active:not(:disabled) {
      transform: none;
    }
  }

  @media (max-width: 640px) {
    .gate-card {
      margin: var(--space-6) -0.5rem;
      padding: 0;
      background: transparent;
      border: 0;
      border-radius: 0;
    }
    .gate-inner {
      border-radius: var(--radius-lg);
      box-shadow: none;
    }
    .gate-head {
      padding: var(--space-4) var(--space-4) var(--space-3);
    }
    .gate-framing {
      padding: var(--space-3) var(--space-3) var(--space-4);
    }
    .framing-head {
      align-items: flex-start;
    }
    .framing-rev {
      text-align: right;
    }
    .gate-segment-row {
      display: grid;
      gap: 0.15rem;
    }
    .gate-segment-meta {
      white-space: normal;
    }
    .gate-action-bar {
      align-items: stretch;
      padding: var(--space-3);
    }
    .gate-action-meta {
      width: 100%;
    }
    .gate-action-main {
      display: grid;
      width: 100%;
      justify-content: stretch;
    }
    .gate-purchase,
    .gate-topup,
    .gate-action-main .gate-error {
      max-width: none;
    }
    .gate-continue-btn {
      justify-content: center;
      width: 100%;
      padding: 0.65rem 0.875rem;
    }
  }
</style>
