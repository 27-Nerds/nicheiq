<script lang="ts">
  import { onMount } from "svelte";
  import {
    MessageCircle,
    Flame,
    TrendingUp,
  } from "lucide-svelte";
  import type { CumulativeStat } from "./artifactParsers";

  interface Props {
    stats: CumulativeStat[];
  }

  let { stats }: Props = $props();

  const iconMap: Record<string, typeof MessageCircle> = {
    MessageCircle,
    Flame,
    TrendingUp,
  };

  const hasAnyValue = $derived(stats.some((s) => s.value != null));

  // Track which stats have been seen to flash on first appearance
  let seenLabels = $state<Set<string>>(new Set());
  let flashLabels = $state<Set<string>>(new Set());

  $effect(() => {
    for (const stat of stats) {
      if (stat.value != null && !seenLabels.has(stat.label)) {
        seenLabels = new Set([...seenLabels, stat.label]);
        flashLabels = new Set([...flashLabels, stat.label]);
        // Remove flash after animation
        setTimeout(() => {
          flashLabels = new Set([...flashLabels].filter((l) => l !== stat.label));
        }, 600);
      }
    }
  });
</script>

{#if hasAnyValue}
  <div class="cumulative-bar">
    {#each stats as stat}
      {@const Icon = iconMap[stat.iconName]}
      <div
        class="stat-item"
        class:has-value={stat.value != null}
        class:flash-in={flashLabels.has(stat.label)}
      >
        {#if Icon}
          <Icon class="stat-icon-svg" />
        {/if}
        <span class="stat-label">{stat.label}</span>
        <span class="stat-value">
          {stat.value != null ? stat.value.toLocaleString() : '--'}
        </span>
      </div>
      {#if stat !== stats[stats.length - 1]}
        <span class="stat-separator">&middot;</span>
      {/if}
    {/each}
  </div>
{/if}

<style>
  .cumulative-bar {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.75rem;
    padding-top: 0.75rem;
    border-top: 1px solid var(--color-border);
    flex-wrap: wrap;
  }

  .stat-item {
    display: flex;
    align-items: baseline;
    gap: 0.375rem;
    padding: 0.125rem 0.375rem;
    border-radius: 0.25rem;
    transition: background 0.3s ease;
  }

  .stat-item:not(.has-value) {
    opacity: 0.4;
  }

  /* Flash animation when a stat first gets a value */
  .stat-item.flash-in {
    animation: stat-flash 600ms ease-out;
  }

  @keyframes stat-flash {
    0% { background: rgba(229, 90, 40, 0.15); }
    100% { background: transparent; }
  }

  :global(.stat-icon-svg) {
    width: 0.875rem;
    height: 0.875rem;
    color: var(--color-text-muted);
    align-self: center;
  }

  .has-value :global(.stat-icon-svg) {
    color: var(--color-accent);
  }

  .stat-label {
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .stat-value {
    font-family: var(--font-mono);
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .stat-separator {
    color: var(--color-text-muted);
    opacity: 0.4;
  }

  @media (prefers-reduced-motion: reduce) {
    .stat-item.flash-in {
      animation: none;
    }
  }
</style>
