<script lang="ts">
  import type { SelectionJourneyTaskStatus } from "$lib/selection/decisionJourney";

  interface Props {
    status: SelectionJourneyTaskStatus;
    label: string;
    /** Compact = sidebar trailing badge; a locked tool renders a lock glyph
     *  instead of the (longer) unlock-hint sentence the launchpad shows. */
    compact?: boolean;
  }

  let { status, label, compact = false }: Props = $props();
</script>

{#if status === "not_ready"}
  {#if compact}
    <span class="decision-status decision-status--lock" aria-label={label} title={label}>
      <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.2" aria-hidden="true"><rect x="2" y="5.5" width="8" height="6" rx="1.5"/><path d="M4 5.5V4a2 2 0 0 1 4 0v1.5"/></svg>
      <span>{label}</span>
    </span>
  {:else}
    <span class="decision-lock">{label}</span>
  {/if}
{:else}
  <span class="decision-status" class:decision-status--compact={compact} data-status={status}>{label}</span>
{/if}

<style>
  .decision-status {
    border-radius: var(--radius-md);
    padding: var(--space-1) var(--space-2);
    color: var(--color-text-secondary);
    background: var(--color-bg-surface);
    font-size: var(--text-xs);
    font-weight: 700;
    white-space: nowrap;
  }
  .decision-status[data-status="recommended"] {
    color: var(--color-info-dark);
    background: var(--color-info-subtle);
  }
  .decision-status[data-status="needs_refresh"] {
    color: var(--color-warning-text);
    background: var(--color-warning-subtle);
  }
  .decision-status--compact[data-status="needs_refresh"] {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    padding: 0;
    background: transparent;
    color: var(--color-text-secondary);
    font-size: var(--text-xs);
    font-weight: 700;
  }
  .decision-status--compact[data-status="needs_refresh"]::before {
    width: var(--space-1-5);
    height: var(--space-1-5);
    border-radius: var(--radius-full);
    background: var(--color-warning-text);
    content: "";
  }
  .decision-status[data-status="complete"] {
    color: var(--color-success-text);
    background: var(--color-success-subtle);
  }
  /* Optional reads as available, not a labelled exception. */
  .decision-status[data-status="optional"] {
    background: transparent;
    padding-inline: 0;
    font-weight: 600;
  }
  .decision-status--lock {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    padding: 0;
    background: transparent;
    color: var(--color-text-muted);
  }
  .decision-status--lock svg {
    width: var(--space-3);
    height: var(--space-3);
  }
  .decision-lock {
    display: block;
    margin-top: var(--space-1);
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    font-weight: 600;
  }
</style>
