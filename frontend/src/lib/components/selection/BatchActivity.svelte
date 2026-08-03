<script lang="ts">
  import { CheckCircle2, CircleX, Clock, Layers3, Loader2, RotateCcw } from "lucide-svelte";
  import type { ActiveJobOperation } from "$lib/api";
  import {
    elapsedClock,
    evaluationProgress,
  } from "$lib/selection/evaluationProgress.svelte";
  import type { BatchActivity as BatchActivityRecord } from "$lib/stores/chatLedger.svelte";

  interface Props {
    activities: BatchActivityRecord[];
    view?: "history" | "live";
    stalledOperationId?: string | null;
    onRecheck?: (activity: BatchActivityRecord) => void;
    onReviewCandidates?: (ideaIds: string[]) => void;
    onReviewRuledOut?: (operationId: string) => void;
    onRetry?: (activity: BatchActivityRecord) => void;
    cancellableOperationId?: string | null;
    cancellingOperationId?: string | null;
    onCancel?: (activity: BatchActivityRecord) => void;
    operation?: ActiveJobOperation | null;
    reviewCandidatesHref?: (activity: BatchActivityRecord) => string;
    reviewRuledOutHref?: (activity: BatchActivityRecord) => string;
    retryHref?: string;
  }

  let {
    activities,
    view = "history",
    stalledOperationId = null,
    onRecheck,
    onReviewCandidates,
    onReviewRuledOut,
    onRetry,
    cancellableOperationId = null,
    cancellingOperationId = null,
    onCancel,
    operation = null,
    reviewCandidatesHref,
    reviewRuledOutHref,
    retryHref,
  }: Props = $props();

  function statusLabel(activity: BatchActivityRecord): string {
    if (isRecovering(activity)) return "Restoring previous candidates";
    if (activity.outcome === "pending") return "Adding another batch";
    if (activity.outcome === "completed") return "Batch added";
    if (activity.outcome === "no_candidates_added") return "No candidates added";
    if (activity.outcome === "refunded") return "Batch refunded";
    if (activity.outcome === "cancelled") return "Batch cancelled";
    return "Batch failed";
  }

  function focusLabel(focus: BatchActivityRecord["focus"]): string {
    if (focus === "novelty") return "Differentiation focus";
    if (focus === "distribution") return "Distribution focus";
    return "Automatic focus";
  }

  function addedCandidateCount(activity: BatchActivityRecord): number {
    return activity.addedCount
      ?? (activity.addedIdeas.length > 0 ? activity.addedIdeas.length : activity.addedIdeaIds.length);
  }

  function canReviewCandidates(activity: BatchActivityRecord): boolean {
    return activity.addedIdeas.length > 0 || activity.addedIdeaIds.length > 0;
  }

  function canReviewRuledOut(activity: BatchActivityRecord): boolean {
    return (activity.ruledOutCount ?? 0) > 0;
  }

  function isStalled(activity: BatchActivityRecord): boolean {
    return activity.outcome === "pending" && activity.operationId === stalledOperationId;
  }

  function isRecovering(activity: BatchActivityRecord): boolean {
    return activity.outcome === "pending"
      && activity.operationId === operation?.id
      && operation.state === "RECOVERING";
  }

  function candidateCount(count: number): string {
    return `${count} ${count === 1 ? "candidate" : "candidates"}`;
  }

  function activitySummary(activity: BatchActivityRecord): string {
    const generated = activity.generatedCount;
    const added = addedCandidateCount(activity);
    const generatedSuffix = generated == null
      ? ""
      : ` after generating ${candidateCount(generated)}`;

    if (activity.outcome === "pending") {
      if (isRecovering(activity)) {
        return "This batch stopped before it settled. We are restoring the candidate set from before it started. After restoration, any refundable credits are returned; if no refund applies, the receipt will say so.";
      }
      if (isStalled(activity)) {
        return "Automatic checks paused. The batch still settles or refunds on its own; check for the latest result, or return later.";
      }
      if (activity.operationId === operation?.id && progress.phase === "queued") {
        return "Waiting for a free worker. Existing candidate scores and your shortlist stay unchanged.";
      }
      if (activity.operationId === operation?.id && progress.phase === "overdue") {
        return "This is taking longer than usual. The batch still finishes or refunds on its own; you can leave and return later.";
      }
      return view === "live"
        ? "Generating and checking new candidates. Existing scores and shortlist stay unchanged."
        : "New candidates are being generated and checked. Existing candidate scores and your shortlist stay unchanged. You can leave this page and return while the batch runs.";
    }
    if (activity.outcome === "completed") {
      const result = generated == null
        ? `Added ${candidateCount(added)}.`
        : `Added ${added} of ${generated} generated ${generated === 1 ? "candidate" : "candidates"}.`;
      return `${result} The ranked list may reorder around the additions.`;
    }
    if (activity.outcome === "no_candidates_added") {
      const result = generated == null
        ? "No generated candidates cleared the checks."
        : `0 of ${generated} generated ${generated === 1 ? "candidate was" : "candidates were"} added.`;
      const ruledOut = activity.ruledOutCount ?? 0;
      return ruledOut > 0
        ? `${result} ${ruledOut} ${ruledOut === 1 ? "idea was" : "ideas were"} retained in the ruled-out analysis.`
        : result;
    }
    if (activity.outcome === "refunded") {
      return `The batch could not complete${generatedSuffix}. Charged credits were refunded, and the existing pool was unchanged.`;
    }
    if (activity.outcome === "cancelled") {
      return activity.refunded
        ? "The batch was cancelled before work started. Charged credits were returned, and the existing pool was unchanged."
        : "The batch was cancelled before work started. The existing pool was unchanged.";
    }
    return `The batch could not complete${generatedSuffix}. The existing pool and shortlist were unchanged.`;
  }

  const visibleActivities = $derived.by(() => {
    const pending = activities.filter((activity) => activity.outcome === "pending");
    if (view === "live") return pending;
    const latestTerminal = activities.find((activity) => activity.outcome !== "pending");
    return latestTerminal && !pending.includes(latestTerminal)
      ? [...pending, latestTerminal]
      : pending;
  });
  const visibleIds = $derived(new Set(visibleActivities.map((activity) => activity.operationId)));
  const olderActivities = $derived(
    view === "history"
      ? activities.filter((activity) => !visibleIds.has(activity.operationId))
      : [],
  );
  const hasPending = $derived(activities.some((activity) => activity.outcome === "pending"));
  $effect(() => {
    if (!hasPending) return;
    elapsedClock.start();
    return () => elapsedClock.stop();
  });
  const progress = $derived(evaluationProgress(operation, elapsedClock.now));
</script>

{#snippet activityIcon(activity: BatchActivityRecord)}
  <div class="status-icon" aria-hidden="true">
    {#if isRecovering(activity)}
      <RotateCcw />
    {:else if isStalled(activity)}
      <Clock />
    {:else if activity.outcome === "pending"}
      <Loader2 class="spin" />
    {:else if activity.outcome === "completed"}
      <CheckCircle2 />
    {:else if activity.outcome === "refunded"}
      <RotateCcw />
    {:else if activity.outcome === "cancelled"}
      <CircleX />
    {:else if activity.outcome === "no_candidates_added"}
      <Layers3 />
    {:else}
      <CircleX />
    {/if}
  </div>
{/snippet}

{#snippet activityCopy(activity: BatchActivityRecord)}
  <div class="batch-copy">
    <div class="batch-heading">
      <strong>{statusLabel(activity)}</strong>
      <span>Batch {activity.ordinal} · {focusLabel(activity.focus)}</span>
      {#if activity.outcome === "pending"}
        <span aria-label={`Elapsed ${progress.elapsedLabel}`}>{progress.elapsedLabel} elapsed</span>
      {/if}
    </div>
    <p>{activitySummary(activity)}</p>
    {#if activity.outcome === "completed" && activity.refPrecision === "legacy_id_only"}
      <p class="legacy-note">This older receipt identifies candidates by ID only. The destination uses their latest available revisions.</p>
    {/if}
    {#if view === "history"}
      <details class="technical-details">
        <summary>Technical details</summary>
        <small>Operation {activity.operationId}</small>
      </details>
    {/if}
  </div>
{/snippet}

{#snippet activityAction(activity: BatchActivityRecord)}
  <div class="batch-action">
    {#if activity.outcome === "pending" && !isRecovering(activity) && activity.operationId === cancellableOperationId && onCancel}
      <button
        type="button"
        disabled={cancellingOperationId === activity.operationId}
        onclick={() => onCancel?.(activity)}
      >
        {cancellingOperationId === activity.operationId ? "Cancelling…" : "Cancel queued batch"}
      </button>
    {:else if isStalled(activity) && onRecheck}
      <button type="button" onclick={() => onRecheck?.(activity)}>Check status</button>
    {:else if activity.outcome === "completed" && canReviewCandidates(activity)}
      {#if onReviewCandidates}
        <button type="button" onclick={() => onReviewCandidates?.(activity.addedIdeaIds)}>Review new candidates</button>
      {:else if reviewCandidatesHref}
        <a href={reviewCandidatesHref(activity)}>Review new candidates</a>
      {/if}
    {:else if activity.outcome === "no_candidates_added" && canReviewRuledOut(activity)}
      {#if onReviewRuledOut}
        <button type="button" onclick={() => onReviewRuledOut?.(activity.operationId)}>Review ruled-out ideas</button>
      {:else if reviewRuledOutHref}
        <a href={reviewRuledOutHref(activity)}>Review ruled-out ideas</a>
      {/if}
    {:else if activity.outcome === "failed" || activity.outcome === "refunded" || activity.outcome === "cancelled"}
      {#if onRetry}
        <button type="button" onclick={() => onRetry(activity)}>Try again</button>
      {:else if retryHref}
        <a href={retryHref}>Try again</a>
      {/if}
    {/if}
  </div>
{/snippet}

{#if (view === "history" && activities.length > 0) || visibleActivities.length > 0}
  <section
    class="batch-activity"
    class:batch-activity--live={view === "live"}
    aria-labelledby={view === "history" ? "batch-activity-title" : undefined}
    aria-label={view === "live" ? "Idea batch in progress" : undefined}
  >
    {#if view === "history"}
      <header>
        <div>
          <p>Additional batches</p>
          <h2 id="batch-activity-title">
            {activities.length} batch {activities.length === 1 ? "run" : "runs"}
          </h2>
        </div>
        <span>Each batch appends results. Existing candidates and your shortlist are never replaced.</span>
      </header>
    {/if}

    <ol>
      {#each visibleActivities as activity (activity.operationId)}
        <li
          class:pending={activity.outcome === "pending"}
          class:complete={activity.outcome === "completed"}
          role={activity.outcome === "pending" ? "status" : undefined}
        >
          {@render activityIcon(activity)}
          {@render activityCopy(activity)}
          {@render activityAction(activity)}
        </li>
      {/each}
    </ol>
    {#if olderActivities.length > 0}
      <details class="batch-history">
        <summary>Batch history ({olderActivities.length})</summary>
        <ol>
          {#each olderActivities as activity (activity.operationId)}
            <li class:complete={activity.outcome === "completed"}>
              {@render activityIcon(activity)}
              {@render activityCopy(activity)}
              {@render activityAction(activity)}
            </li>
          {/each}
        </ol>
      </details>
    {/if}
  </section>
{/if}

<style>
  .batch-activity {
    display: grid;
    gap: var(--space-3);
    margin-bottom: var(--space-4);
    padding: var(--space-4);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-bg-surface);
  }
  .batch-activity--live {
    gap: 0;
    padding: var(--space-2) var(--space-3);
  }
  .batch-activity--live ol { border-top: 0; }
  .batch-activity--live li {
    align-items: center;
    padding: var(--space-2) 0;
    border-bottom: 0;
  }
  header { display: flex; align-items: end; justify-content: space-between; gap: var(--space-6); }
  header > div { display: grid; gap: var(--space-1); }
  header p {
    margin: 0;
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: var(--tracking-wide);
    text-transform: uppercase;
  }
  header h2 { margin: 0; color: var(--color-text-primary); font-family: var(--font-display); font-size: var(--text-md); line-height: var(--leading-tight); }
  header > span { max-width: 50ch; color: var(--color-text-secondary); font-size: var(--text-sm); line-height: var(--leading-normal); text-align: right; text-wrap: pretty; }
  ol { display: grid; margin: 0; padding: 0; border-top: 1px solid var(--color-border); list-style: none; }
  li {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    gap: var(--space-3);
    align-items: start;
    padding: var(--space-3) 0;
    border-bottom: 1px solid var(--color-border);
  }
  li:last-child { padding-bottom: 0; border-bottom: 0; }
  .status-icon { display: grid; place-items: center; width: 1.8rem; height: 1.8rem; color: var(--color-error-text); }
  .status-icon :global(svg) { width: 1rem; height: 1rem; }
  li.pending .status-icon { color: var(--color-info-dark); }
  li.complete .status-icon { color: var(--color-success-text); }
  .batch-copy { display: grid; gap: var(--space-1); min-width: 0; }
  .batch-heading { display: flex; flex-wrap: wrap; align-items: baseline; gap: var(--space-2); }
  .batch-heading strong { color: var(--color-text-primary); font-size: var(--text-sm); }
  .batch-heading span, small { color: var(--color-text-secondary); font-family: var(--font-mono); font-size: var(--text-xs); font-variant-numeric: tabular-nums; }
  .batch-copy p { max-width: 70ch; margin: 0; color: var(--color-text-secondary); font-size: var(--text-sm); line-height: var(--leading-normal); text-wrap: pretty; }
  .technical-details summary, .batch-history > summary {
    width: fit-content;
    color: var(--color-text-secondary);
    font-size: var(--text-xs);
    cursor: pointer;
  }
  .technical-details small { display: block; margin-top: var(--space-1); word-break: break-all; }
  .batch-history { border-top: 1px solid var(--color-border); padding-top: var(--space-3); }
  .batch-history > summary { min-height: var(--space-8); font-size: var(--text-sm); font-weight: 700; }
  .batch-history ol { margin-top: var(--space-2); }
  .batch-action { align-self: center; }
  button, a {
    display: inline-flex;
    align-items: center;
    min-height: 2rem;
    padding: 0 var(--space-2);
    border: 0;
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--color-accent-dark);
    font: inherit;
    font-size: var(--text-sm);
    font-weight: 700;
    text-decoration: none;
    cursor: pointer;
  }
  button:hover, a:hover { background: var(--color-bg-surface); }
  button:disabled { opacity: 0.55; cursor: wait; }
  button:active, a:active { transform: scale(0.98); }
  button:focus-visible, a:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  :global(.spin) { animation: spin var(--duration-slowest) linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  @media (max-width: 720px) {
    header { align-items: start; flex-direction: column; gap: var(--space-2); }
    header > span { text-align: left; }
    li { grid-template-columns: auto minmax(0, 1fr); }
    .batch-action { grid-column: 1 / -1; }
    .batch-action button, .batch-action a {
      justify-content: center;
      width: 100%;
      min-height: 2.75rem;
      border: 1px solid var(--color-border);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    :global(.spin) { animation: none; }
    button:active, a:active { transform: none; }
  }
</style>
