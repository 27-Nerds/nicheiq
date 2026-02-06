<script lang="ts">
  import type { Snippet } from "svelte";

  interface Props {
    children: Snippet;
    class?: string;
    title?: string;
  }

  let { children, class: className = "", title }: Props = $props();
</script>

<div class="chart-wrapper {className}">
  {#if title}
    <h4 class="chart-title">{title}</h4>
  {/if}
  <div class="chart-content">
    {@render children()}
  </div>
</div>

<style>
  .chart-wrapper {
    --chart-grid: rgba(255, 255, 255, 0.06);
    --chart-axis: var(--color-text-muted);
    --chart-text: var(--color-text-secondary);
    --chart-accent: var(--color-accent);
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 12px;
    padding: 1.5rem;
  }

  .chart-title {
    font-family: var(--font-body);
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin-bottom: 1rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .chart-content {
    position: relative;
    width: 100%;
  }

  /* LayerChart axis styling */
  .chart-wrapper :global(text) {
    fill: var(--chart-text);
    font-family: var(--font-mono);
    font-size: 0.6875rem;
  }

  .chart-wrapper :global(.axis-label) {
    fill: var(--color-text-muted);
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  /* Grid lines */
  .chart-wrapper :global(.grid line),
  .chart-wrapper :global(.gridlines line) {
    stroke: var(--chart-grid);
    stroke-dasharray: 2 4;
  }

  /* Axis lines */
  .chart-wrapper :global(.axis line),
  .chart-wrapper :global(.axis path) {
    stroke: var(--color-border);
  }

  /* Tooltip styling */
  .chart-wrapper :global(.tooltip) {
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border-emphasis);
    border-radius: 8px;
    padding: 0.75rem 1rem;
    box-shadow: var(--shadow-lg);
    font-family: var(--font-body);
    font-size: 0.8125rem;
    color: var(--color-text-primary);
  }

  /* Point/marker hover effects */
  .chart-wrapper :global(circle),
  .chart-wrapper :global(rect) {
    transition: all 0.2s ease-out;
  }

  .chart-wrapper :global(circle:hover),
  .chart-wrapper :global(rect:hover) {
    filter: brightness(1.2);
  }

  /* Animation for chart elements */
  @keyframes chart-fade-in {
    from {
      opacity: 0;
      transform: translateY(10px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .chart-wrapper :global(.animate-in) {
    animation: chart-fade-in 0.5s ease-out forwards;
  }
</style>
