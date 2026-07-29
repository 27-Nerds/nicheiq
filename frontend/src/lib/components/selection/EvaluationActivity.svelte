<script lang="ts">
  import { CheckCircle2, CircleX, Clock, Loader2, RotateCcw } from "lucide-svelte";
  import type { SeedActivity } from "$lib/stores/chatLedger.svelte";
  import {
    elapsedClock,
    evaluationProgress,
    phaseHeadline,
    phaseNote,
    type EvaluationOperation,
  } from "$lib/selection/evaluationProgress.svelte";

  /**
   * Two views over the SAME durable receipts, split by lifecycle rather than by feature.
   *
   * - `live` sits above the candidate pool and shows ONLY evaluations still running. That
   *   is the one state with real urgency: it is time-boxed and it explains why the pool
   *   controls are locked.
   * - `record` sits with the Discovery appendix, beside "Examined & ruled out", and holds
   *   settled evaluations. A settled result has no urgency left and its content already
   *   lives elsewhere — accepted directions become ranked candidates, demoted ones become
   *   ruled-out findings — so this is a provenance ledger pointing at those homes, not a
   *   second copy of them above the fold.
   */
  interface Props {
    jobId: string;
    activities: SeedActivity[];
    view: "live" | "record" | "handoff";
    /** The job's active dispatch. `claimedAt` is what separates "queued behind other
     *  work" from "a worker is on it" — without it every wait looks identical. */
    operation?: EvaluationOperation | null;
    /** The automatic poll gave up. It used to stop silently, leaving the pool locked
     *  until a manual page reload; now the wait says so and offers a re-check. */
    stalled?: boolean;
    onRecheck?: () => void;
    /** Opens the collapsed Examined-and-ruled-out list. Record view only. */
    onOpenRuledOut?: () => void;
    /** Routed handoff: the job hub remains the only place that may apply it. */
    onProposeCandidate?: (activity: SeedActivity) => void;
  }

  let {
    jobId,
    activities,
    view,
    operation = null,
    stalled = false,
    onRecheck,
    onOpenRuledOut,
    onProposeCandidate,
  }: Props = $props();

  const shown = $derived.by(() => {
    if (view === "live") return activities.filter((activity) => activity.outcome === "pending");
    const settled = activities.filter((activity) => activity.outcome !== "pending");
    return view === "handoff" ? settled.slice(0, 1) : settled;
  });

  // Only run the shared 1s clock while something is actually waiting.
  $effect(() => {
    if (view !== "live" || shown.length === 0) return;
    elapsedClock.start();
    return () => elapsedClock.stop();
  });

  const progress = $derived(evaluationProgress(operation, elapsedClock.now));

  function outcomeLabel(outcome: SeedActivity["outcome"]): string {
    if (outcome === "accepted") return "Added to candidates";
    if (outcome === "demoted") return "Did not qualify";
    if (outcome === "refunded") return "Refunded";
    return "Evaluation failed";
  }

  /** Where the result actually lives now, so the row can point instead of restate. */
  function destinationNote(outcome: SeedActivity["outcome"]): string {
    if (outcome === "accepted") return "It is in the ranked candidates above.";
    if (outcome === "demoted") return "The full analysis is kept with the ideas you screened out.";
    if (outcome === "refunded") return "No candidate was produced. Your credits were returned.";
    return "No candidate was produced.";
  }

  function scoreLabel(score: number | undefined): string | null {
    if (score == null || !Number.isFinite(score)) return null;
    return `${Math.round(score * 100)} market fit`;
  }

  function titleOf(activity: SeedActivity): string {
    return activity.proposedTitle ?? activity.result?.proposed_title ?? "Custom direction";
  }
</script>

{#if shown.length > 0}
  {#if view === "live"}
    <!-- One status line per running evaluation. Not a card: nothing here outranks the
         candidate list, it only reports what is happening and why controls are locked. -->
    <section class="evaluation-live" aria-label="Evaluation in progress">
      {#each shown as activity (activity.evaluationId ?? activity.sourceMessageId)}
        <p class="live-row" class:overdue={progress.phase === "overdue"} role="status">
          {#if progress.phase === "queued"}
            <Clock aria-hidden="true" />
          {:else}
            <Loader2 class="spin" aria-hidden="true" />
          {/if}
          <span class="live-title">{phaseHeadline(progress.phase, titleOf(activity))}</span>
          <span class="live-elapsed" aria-label={`Elapsed ${progress.elapsedLabel}`}>
            {progress.elapsedLabel}
          </span>
          <span class="live-note">
            {#if stalled}
              We stopped checking automatically. The evaluation still settles or refunds
              on its own — check for the result, or reload later.
            {:else}
              {phaseNote(progress.phase)}
            {/if}
          </span>
          {#if stalled && onRecheck}
            <button type="button" class="live-recheck" onclick={onRecheck}>
              Check for the result
            </button>
          {/if}
        </p>
      {/each}
    </section>
  {:else}
    <section
      class="evaluation-record"
      class:evaluation-record--handoff={view === "handoff"}
      id={view === "handoff" ? "evaluation-result" : "evaluation-record"}
      aria-labelledby={view === "handoff" ? "evaluation-result-title" : "evaluation-record-title"}
      aria-live={view === "handoff" ? "polite" : undefined}
    >
      <header>
        <span class="record-kicker">{view === "handoff" ? "Evaluation complete" : "Evaluation history"}</span>
        <h3 id={view === "handoff" ? "evaluation-result-title" : "evaluation-record-title"}>
          {view === "handoff" ? "Your direction has a result" : "Directions you sent for evaluation"}
        </h3>
        <p>
          {view === "handoff"
            ? "The result is durable and remains available in the job record."
            : "Each direction was scored on its own. Accepted directions joined the ranked candidates; the rest are kept here with the reason they did not."}
        </p>
      </header>

      <ol>
        {#each shown as activity (activity.evaluationId ?? activity.sourceMessageId)}
          {@const evaluatedTitle = activity.result?.solution_name}
          {@const score = scoreLabel(activity.result?.market_fit_score)}
          <li class:accepted={activity.outcome === "accepted"}>
            <div class="status-icon" aria-hidden="true">
              {#if activity.outcome === "accepted"}
                <CheckCircle2 />
              {:else if activity.outcome === "refunded"}
                <RotateCcw />
              {:else}
                <CircleX />
              {/if}
            </div>
            <div class="activity-copy">
              <div class="activity-heading">
                <strong>{outcomeLabel(activity.outcome)}</strong>
                {#if score}<span>{score}</span>{/if}
              </div>
              <p class="title">{titleOf(activity)}</p>
              {#if evaluatedTitle && evaluatedTitle !== activity.proposedTitle}
                <p class="result-title"><span>Evaluated result</span>{evaluatedTitle}</p>
              {/if}
              <p class="destination">{destinationNote(activity.outcome)}</p>
              <details>
                <summary>Review evaluation</summary>
                <div class="evaluation-detail">
                  {#if activity.result?.reason}
                    <p>{activity.result.reason}</p>
                  {:else if activity.outcome === "accepted"}
                    <p>This direction cleared the market-fit check and was appended to the candidate pool.</p>
                  {:else if activity.outcome === "demoted"}
                    <p>This direction was evaluated but did not clear the market-fit check.</p>
                  {:else}
                    <p>The evaluation did not produce a candidate. Any charged credits were refunded.</p>
                  {/if}
                  {#if activity.evaluationId}
                    <small>Evaluation {activity.evaluationId}</small>
                  {/if}
                </div>
              </details>
            </div>
            {#if activity.outcome === "accepted"}
              {#if view === "handoff" && onProposeCandidate}
                <button type="button" class="goto" onclick={() => onProposeCandidate?.(activity)}>
                  Review for shortlist <span aria-hidden="true">→</span>
                </button>
              {:else}
                <a href={activity.result?.idea_id
                  ? `/jobs/${jobId}?detailTab=overview&ideaId=${encodeURIComponent(activity.result.idea_id)}&ideaRevision=${activity.result.idea_revision ?? 1}`
                  : `/jobs/${jobId}#opportunities`}
                >View candidate <span aria-hidden="true">→</span></a>
              {/if}
            {:else if activity.outcome === "demoted"}
              {#if activity.evaluationId}
                <a href={`/jobs/${jobId}?evaluationId=${encodeURIComponent(activity.evaluationId)}#examined-ruled-out`}>
                  Review screened-out result <span aria-hidden="true">→</span>
                </a>
              {:else if onOpenRuledOut}
                <button type="button" class="goto" onclick={onOpenRuledOut}>
                  Open screened out <span aria-hidden="true">→</span>
                </button>
              {/if}
            {/if}
          </li>
        {/each}
      </ol>
    </section>
  {/if}
{/if}

<style>
  /* ── live ── */
  .evaluation-live {
    display: grid;
    gap: var(--space-2);
    margin-bottom: var(--space-4);
  }
  .live-row {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: var(--space-1) var(--space-3);
    margin: 0;
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-bg-surface);
  }
  .live-row :global(svg) {
    width: 0.9rem;
    height: 0.9rem;
    align-self: center;
    color: var(--color-info-dark);
  }
  .live-title {
    color: var(--color-text-primary);
    font-size: var(--text-sm);
    font-weight: 600;
  }
  .live-note {
    flex-basis: 100%;
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: var(--leading-normal);
    text-wrap: pretty;
  }
  .live-elapsed {
    margin-left: auto;
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-variant-numeric: tabular-nums;
  }
  /* Severity amber, not error red: an overdue evaluation has not failed — it still
     settles or refunds on its own, so it must not read as a failure. Icon and border
     only; the amber is never used for text. */
  .live-row.overdue { border-color: var(--color-warning-text); }
  .live-row.overdue :global(svg) { color: var(--color-warning-text); }
  .live-recheck {
    min-height: 2rem;
    padding: 0 var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    background: var(--color-bg-surface);
    color: var(--color-text-primary);
    font-family: inherit;
    font-size: var(--text-sm);
    font-weight: 700;
    cursor: pointer;
  }
  .live-recheck:hover { border-color: var(--color-input-border-hover); background: var(--color-bg-surface); }
  .live-recheck:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }

  /* ── record ── */
  .evaluation-record {
    display: grid;
    gap: var(--space-3);
    padding: var(--space-4);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-bg-surface);
  }
  header { display: grid; gap: var(--space-1); }
  .record-kicker {
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: var(--tracking-wide);
    text-transform: uppercase;
  }
  header h3 {
    margin: 0;
    color: var(--color-text-primary);
    font-family: var(--font-display);
    font-size: var(--text-md);
    line-height: var(--leading-tight);
  }
  header p {
    max-width: 68ch;
    margin: 0;
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: var(--leading-normal);
    text-wrap: pretty;
  }
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
  .status-icon {
    display: grid;
    place-items: center;
    width: 1.8rem;
    height: 1.8rem;
    color: var(--color-error-text);
  }
  .status-icon :global(svg) { width: 1rem; height: 1rem; }
  li.accepted .status-icon { color: var(--color-success-text); }
  .activity-copy { display: grid; gap: var(--space-1); min-width: 0; }
  .activity-heading { display: flex; flex-wrap: wrap; align-items: baseline; gap: var(--space-2); }
  .activity-heading strong { color: var(--color-text-primary); font-size: var(--text-sm); }
  .activity-heading span {
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-variant-numeric: tabular-nums;
  }
  .title { margin: 0; color: var(--color-text-primary); font-size: var(--text-sm); font-weight: 600; }
  .destination, .result-title {
    margin: 0;
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: var(--leading-normal);
    text-wrap: pretty;
  }
  .result-title span {
    margin-right: var(--space-2);
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: var(--tracking-wide);
    text-transform: uppercase;
  }
  details { margin-top: var(--space-1); }
  summary {
    width: fit-content;
    color: var(--color-accent-dark);
    font-size: var(--text-sm);
    font-weight: 700;
    cursor: pointer;
    text-underline-offset: 0.2em;
  }
  summary:hover { text-decoration: underline; }
  summary:focus-visible, a:focus-visible, .goto:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .evaluation-detail { display: grid; gap: var(--space-2); max-width: 68ch; padding-top: var(--space-2); }
  .evaluation-detail p { margin: 0; color: var(--color-text-secondary); font-size: var(--text-sm); line-height: var(--leading-normal); }
  .evaluation-detail small { color: var(--color-text-muted); font-family: var(--font-mono); font-size: var(--text-xs); word-break: break-all; }
  a {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    min-height: 2rem;
    color: var(--color-accent-dark);
    font-size: var(--text-sm);
    font-weight: 700;
    text-decoration: none;
  }
  a:hover { text-decoration: underline; text-underline-offset: 0.2em; }
  .goto {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    min-height: 2rem;
    padding: 0;
    border: 0;
    background: none;
    color: var(--color-accent-dark);
    font-family: inherit;
    font-size: var(--text-sm);
    font-weight: 700;
    cursor: pointer;
  }
  .goto:hover { text-decoration: underline; text-underline-offset: 0.2em; }
  :global(.spin) { animation: spin var(--duration-slowest) linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  @media (max-width: 720px) {
    li { grid-template-columns: auto minmax(0, 1fr); }
    li > a, li > .goto { grid-column: 2; }
  }
  @media (prefers-reduced-motion: reduce) {
    :global(.spin) { animation: none; }
  }
</style>
