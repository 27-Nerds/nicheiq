<script lang="ts">
  // SYSTEM activity row for the analyst ledger. Two voices, two treatments:
  // LIVE = the pipeline is running — mono status line with the percent in
  // info-blue plus a swept progress hairline (the machine's working idiom,
  // borrowed from ResearchProgressScreen — never a spinner, never the analyst's
  // block-caret). FROZEN = a completed run's boundary marker — one muted mono
  // line opened by a green check, matching the ledger's closed-history spine.
  interface Props {
    live?: boolean;
    text: string;
    /** Live only — 0-100; omitted (or stale) hides the percent + bar fill. */
    percent?: number | null;
    /** Live only — no SSE update for >45s: drop the percent, soften the copy. */
    stale?: boolean;
  }

  let { live = false, text, percent = null, stale = false }: Props = $props();

  const pct = $derived(
    !stale && typeof percent === "number" ? Math.max(0, Math.min(100, Math.round(percent))) : null,
  );
</script>

<div class="activity entry-grid" class:is-live={live}>
  <span class="activity-tag">SYSTEM</span>
  <div class="activity-body">
    {#if live}
      <p class="activity-line" role="status" aria-live="polite">
        {text}{#if pct !== null}&nbsp;&middot; <span class="activity-pct">{pct}%</span>{/if}
      </p>
      <div
        class="activity-track"
        role="progressbar"
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow={pct ?? undefined}
        aria-label="Research progress"
      >
        <div class="activity-fill" style:width="{pct ?? 4}%"></div>
        <div class="activity-sweep" aria-hidden="true"></div>
      </div>
    {:else}
      <p class="activity-frozen"><span class="ledger-check" aria-hidden="true">&#10003;</span> {text}</p>
    {/if}
  </div>
</div>

<style>
  /* Same tag column and gutter as ChatThread's entries — shared tokens, because the
     two render as adjacent rows and a copy-pasted magic number had already drifted. */
  .entry-grid {
    display: grid;
    grid-template-columns: var(--ledger-tag-col) minmax(0, 1fr);
    gap: var(--space-2);
    padding: 0.6rem var(--ledger-gutter);
  }
  .activity {
    border-top: 1px solid var(--color-border);
  }
  .activity-tag {
    padding-top: var(--space-1);
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 800;
    letter-spacing: 0.06em;
    color: var(--color-text-muted);
  }
  .activity-body {
    display: grid;
    gap: var(--space-1-5);
    min-width: 0;
  }
  .activity-line {
    margin: 0;
    font-family: var(--font-mono);
    font-size: 0.75rem;
    font-weight: 500;
    font-variant-numeric: tabular-nums;
    color: var(--color-text-secondary);
  }
  .activity-pct {
    font-weight: 700;
    color: var(--color-info-dark);
  }
  .activity-track {
    position: relative;
    height: 3px;
    border-radius: 2px;
    background: var(--color-border);
    overflow: hidden;
  }
  .activity-fill {
    height: 100%;
    background: var(--color-info);
    border-radius: 2px;
    /* Continuous SSE data, not a state change — exempt from the 240ms cap. */
    transition: width 600ms cubic-bezier(0.4, 0, 0.2, 1);
  }
  .activity-sweep {
    position: absolute;
    inset: 0;
    background: linear-gradient(
      90deg,
      transparent,
      color-mix(in srgb, var(--color-info) 50%, transparent),
      transparent
    );
    animation: activity-sweep 1.8s ease-in-out infinite;
  }
  @keyframes activity-sweep {
    from { transform: translateX(-100%); }
    to { transform: translateX(100%); }
  }
  .activity-frozen {
    margin: 0;
    font-family: var(--font-mono);
    font-size: 0.75rem;
    font-weight: 500;
    font-variant-numeric: tabular-nums;
    color: var(--color-text-muted);
  }

  @media (prefers-reduced-motion: reduce) {
    .activity-sweep { animation: none; opacity: 0; }
    .activity-fill { transition: none; }
  }
</style>
