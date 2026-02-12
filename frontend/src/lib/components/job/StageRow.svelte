<script lang="ts">
  import { Minus } from "lucide-svelte";
  import type { StageProgress } from "$lib/types/job";
  import type { CelebrationTier } from "./phaseConfig";

  interface Props {
    stage: StageProgress;
    narrativeText?: string;
    isLast?: boolean;
    celebrationTier?: CelebrationTier;
  }

  let {
    stage,
    narrativeText,
    isLast = false,
    celebrationTier = 1,
  }: Props = $props();

  const displayText = $derived(narrativeText || stage.stageName);
  const isCompleted = $derived(stage.status === 'COMPLETED');

  function formatDuration(seconds: number | null): string {
    if (!seconds) return "";
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const totalSeconds = Math.round(seconds);
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${mins}m ${secs}s`;
  }
</script>

<div
  class="stage-row"
  class:is-running={stage.status === 'RUNNING'}
  class:is-completed={isCompleted}
  class:is-failed={stage.status === 'FAILED'}
  class:is-last={isLast}
  class:celebration-t2={isCompleted && celebrationTier >= 2}
>
  <!-- Dot -->
  <div class="dot dot-{stage.status.toLowerCase()}">
    {#if stage.status === "SKIPPED"}
      <Minus class="dot-icon dot-icon-muted" />
    {/if}
  </div>

  <!-- Text + duration -->
  <span
    class="stage-name"
    class:text-info={stage.status === 'RUNNING'}
    class:text-primary={stage.status === 'COMPLETED'}
    class:text-secondary={stage.status !== 'RUNNING' && stage.status !== 'COMPLETED'}
  >
    {displayText}
  </span>

  {#if stage.durationSeconds}
    <span class="duration">{formatDuration(stage.durationSeconds)}</span>
  {/if}

  <!-- Green glow overlay for completion -->
  {#if isCompleted}
    <div class="completion-glow"></div>
  {/if}
</div>

<style>
  .stage-row {
    display: flex;
    align-items: flex-start;
    gap: 0.625rem;
    padding: 0.5rem 0.25rem;
    position: relative;
    overflow: visible;
    border-radius: 0.375rem;
    transition: background 0.15s ease;
  }

  /* Vertical connector segment from this dot down to the next row's dot */
  .stage-row::before {
    content: '';
    position: absolute;
    left: calc(0.25rem + 0.375rem); /* dot horizontal center (padding-left + half of 0.75rem dot) */
    top: calc(0.5rem + 0.1875rem + 0.75rem); /* starts at dot bottom edge (padding-top + margin-top + dot height) */
    bottom: calc(-0.125rem - 0.5rem - 0.1875rem); /* extends through gap + next row padding-top + next dot margin-top */
    width: 1.5px;
    background: var(--color-border);   /* default: grey (pending) */
    z-index: 0;
    pointer-events: none;
  }

  /* Color connector by status */
  .stage-row.is-completed::before {
    background: rgba(34, 197, 94, 0.25);
  }
  .stage-row.is-running::before {
    background: rgba(59, 130, 246, 0.25);
  }
  .stage-row.is-failed::before {
    background: rgba(239, 68, 68, 0.25);
  }

  /* Last row has no connector below */
  .stage-row.is-last::before {
    display: none;
  }

  .stage-row.is-running {
    background: rgba(59, 130, 246, 0.06);
    background-image: linear-gradient(90deg, transparent, rgba(59, 130, 246, 0.12), transparent);
    background-size: 200% 100%;
    animation: running-shimmer 4s ease-in-out infinite alternate;
  }

  @keyframes running-shimmer {
    0% { background-position: -100% 0; }
    100% { background-position: 200% 0; }
  }

  .completion-glow {
    position: absolute;
    inset: 0;
    background: rgba(34, 197, 94, 0.08);
    border-radius: 0.375rem;
    overflow: hidden;
    animation: glow-fade 600ms ease-out forwards;
    pointer-events: none;
  }

  @keyframes glow-fade {
    0% { opacity: 1; }
    100% { opacity: 0; }
  }

  .celebration-t2 .duration {
    animation: value-highlight 500ms ease-out;
  }

  @keyframes value-highlight {
    0% { background: rgba(229, 90, 40, 0.15); border-radius: 4px; }
    100% { background: transparent; }
  }

  .dot {
    width: 0.75rem;
    height: 0.75rem;
    margin-top: 0.1875rem; /* vertically align dot center with text center */
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    flex-shrink: 0;
    position: relative;
    z-index: 1;
  }

  .dot-completed {
    background: rgba(34, 197, 94, 0.45);
    border: 1px solid rgba(34, 197, 94, 0.55);
  }

  .dot-running {
    background: rgba(59, 130, 246, 0.45);
    border: 1px solid rgba(59, 130, 246, 0.55);
  }

  .dot-failed {
    background: rgba(239, 68, 68, 0.45);
    border: 1px solid rgba(239, 68, 68, 0.55);
  }

  .dot-skipped {
    width: 0.875rem;
    height: 0.875rem;
    margin-top: 0.125rem; /* re-center larger skipped dot with text */
    margin-left: -0.0625rem; /* keep dot center aligned with connector */
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
  }

  .dot-pending {
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
  }

  :global(.dot-icon) {
    width: 0.5rem;
    height: 0.5rem;
  }

  :global(.dot-icon-muted) { color: var(--color-text-muted); }

  .stage-name {
    font-size: 0.875rem;
    font-weight: 500;
    line-height: 1.3;
    flex: 1;
    min-width: 0;
  }

  .text-info { color: var(--color-info); }
  .text-primary { color: var(--color-text-primary); }
  .text-secondary { color: var(--color-text-secondary); }

  .duration {
    font-size: 0.8125rem;
    font-family: var(--font-mono);
    color: var(--color-text-muted);
    flex-shrink: 0;
    padding: 0.125rem 0.25rem;
  }

  @media (prefers-reduced-motion: reduce) {
    .check-spring { animation: none; }
    .completion-glow { animation: none; opacity: 0; }
    .celebration-t2 .duration { animation: none; }
    .stage-row.is-running { animation: none; background-image: none; }
  }
</style>
