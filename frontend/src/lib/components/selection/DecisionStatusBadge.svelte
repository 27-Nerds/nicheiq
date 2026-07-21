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
    </span>
  {:else}
    <span class="decision-lock">{label}</span>
  {/if}
{:else}
  <span class="decision-status" data-status={status}>{label}</span>
{/if}

<style>
  .decision-status {
    border-radius: var(--radius-md);
    padding: 0.28rem 0.52rem;
    color: var(--color-text-secondary);
    background: var(--color-bg-surface);
    font-size: 0.66rem;
    font-weight: 750;
    white-space: nowrap;
  }
  .decision-status[data-status="recommended"],
  .decision-status[data-status="needs_refresh"] {
    color: var(--color-accent-dark);
    background: color-mix(in srgb, var(--color-accent) 7%, var(--color-bg-elevated));
  }
  .decision-status[data-status="complete"] {
    color: var(--color-success-dark);
    background: color-mix(in srgb, var(--color-success-dark) 8%, var(--color-bg-elevated));
  }
  /* Optional reads as available, not a labelled exception. */
  .decision-status[data-status="optional"] {
    background: transparent;
    padding-inline: 0;
    font-weight: 600;
  }
  .decision-status--lock {
    display: inline-flex;
    padding: 0;
    background: transparent;
    color: var(--color-text-muted);
  }
  .decision-status--lock svg {
    width: 0.75rem;
    height: 0.75rem;
    opacity: 0.6;
  }
  .decision-lock {
    display: block;
    margin-top: 0.2rem;
    color: var(--color-text-secondary);
    font-size: 0.72rem;
    font-weight: 600;
  }
</style>
