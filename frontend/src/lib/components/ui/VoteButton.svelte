<script lang="ts">
  import { Heart } from "lucide-svelte";

  interface Props {
    label: string;
    count: number;
    total: number;
    voted: boolean;
    onVote: () => void;
    voting?: boolean;
    compact?: boolean;
  }

  let { label, count, total, voted, onVote, voting = false, compact = false }: Props = $props();

  const votePercent = $derived(total > 0 ? Math.round((count / total) * 100) : 0);
  const accessibleLabel = $derived(
    `${voted ? "Your vote: " : "Vote for "}${label}. ${count} ${count === 1 ? "vote" : "votes"}`,
  );

  function handleClick(e: MouseEvent) {
    e.stopPropagation();
    onVote();
  }
</script>

<div class="vote-control">
  <button
    type="button"
    onclick={handleClick}
    disabled={voting}
    class="vote-button"
    class:vote-button--selected={voted}
    aria-label={accessibleLabel}
    aria-pressed={voted}
    aria-busy={voting}
  >
    <Heart class="vote-icon {voted ? 'filled' : ''}" aria-hidden="true" />
    <span>{count}</span>
  </button>
  {#if total > 0 && !compact}
    <div class="vote-share">
      <div class="vote-track" aria-hidden="true">
        <div
          class="vote-fill"
          class:vote-fill--selected={voted}
          style="width: {votePercent}%"
        ></div>
      </div>
      <span>{votePercent}%</span>
    </div>
  {/if}
</div>

<style>
  .vote-control {
    display: flex;
    flex-direction: column;
    gap: var(--space-1-5);
  }

  .vote-button {
    display: inline-flex;
    flex: 0 0 auto;
    align-items: center;
    gap: var(--space-1-5);
    min-height: var(--space-8);
    padding: var(--space-1) var(--space-2);
    border: 1px solid var(--color-input-border);
    border-radius: var(--radius-full);
    background: var(--color-bg-elevated);
    color: var(--color-text-secondary);
    font-family: var(--font-body);
    font-size: var(--text-sm);
    font-weight: 600;
    cursor: pointer;
    transition:
      color var(--duration-fast) var(--ease-default),
      border-color var(--duration-fast) var(--ease-default),
      background-color var(--duration-fast) var(--ease-default),
      transform var(--duration-fast) var(--ease-default);
  }

  .vote-button:hover:not(:disabled) {
    border-color: var(--color-accent-dark);
    color: var(--color-accent-dark);
  }

  .vote-button:active:not(:disabled) {
    transform: scale(0.98);
  }

  .vote-button:focus-visible {
    outline: 2px solid var(--color-accent-dark);
    outline-offset: 2px;
  }

  .vote-button:disabled {
    cursor: wait;
    opacity: 0.65;
  }

  .vote-button--selected {
    border-color: var(--color-accent-dark);
    background: var(--color-accent-subtle);
    color: var(--color-accent-dark);
  }

  :global(.vote-icon) {
    width: 0.875rem;
    height: 0.875rem;
  }

  :global(.vote-icon.filled) {
    fill: currentColor;
  }

  .vote-share {
    display: flex;
    align-items: center;
    gap: var(--space-1-5);
    color: var(--color-text-muted);
    font-size: var(--text-xs);
    font-variant-numeric: tabular-nums;
  }

  .vote-track {
    flex: 1;
    height: var(--space-1-5);
    overflow: hidden;
    border-radius: var(--radius-full);
    background: var(--color-bg-elevated);
  }

  .vote-fill {
    height: 100%;
    border-radius: inherit;
    background: color-mix(in srgb, var(--color-text-muted) 30%, transparent);
    transition: width var(--duration-normal) var(--ease-default);
  }

  .vote-fill--selected {
    background: var(--color-accent-dark);
  }

  @media (prefers-reduced-motion: reduce) {
    .vote-button,
    .vote-fill {
      transition: none;
    }
  }
</style>
