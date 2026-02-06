<script lang="ts">
  import { scaleLinear, scaleBand } from "d3-scale";
  import ChartTheme from "./ChartTheme.svelte";

  interface Props {
    tier0Count: number;
    tier1Count: number;
    tier2Count: number;
    tier3Count: number;
    tier4Count: number;
    class?: string;
  }

  let {
    tier0Count,
    tier1Count,
    tier2Count,
    tier3Count,
    tier4Count,
    class: className = "",
  }: Props = $props();

  // Tier configuration
  const tierConfig = [
    {
      tier: 0,
      label: "Quick Wins",
      color: "var(--viz-cat-1)",
      description: "Low competition, high value",
    },
    {
      tier: 1,
      label: "Growth",
      color: "var(--viz-cat-2)",
      description: "Building momentum",
    },
    {
      tier: 2,
      label: "Competitive",
      color: "var(--viz-cat-3)",
      description: "High competition targets",
    },
    {
      tier: 3,
      label: "Long-term",
      color: "var(--viz-cat-4)",
      description: "Future opportunities",
    },
    {
      tier: 4,
      label: "Monitor",
      color: "var(--viz-cat-5)",
      description: "Watch for changes",
    },
  ];

  const counts = $derived([
    tier0Count,
    tier1Count,
    tier2Count,
    tier3Count,
    tier4Count,
  ]);
  const maxCount = $derived(Math.max(...counts, 1));
  const totalCount = $derived(counts.reduce((a, b) => a + b, 0));

  // Chart data
  const chartData = $derived(
    tierConfig.map((config, i) => ({
      ...config,
      count: counts[i],
      percentage: totalCount > 0 ? (counts[i] / totalCount) * 100 : 0,
    })),
  );

  // Chart dimensions
  const width = 500;
  const height = 280;
  const margin = { top: 20, right: 80, bottom: 20, left: 100 };
  const innerWidth = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;

  // Scales
  const xScale = $derived(
    scaleLinear().domain([0, maxCount]).range([0, innerWidth]),
  );
  const yScale = $derived(
    scaleBand()
      .domain(chartData.map((d) => d.label))
      .range([0, innerHeight])
      .padding(0.35),
  );

  // Hover state
  let hoveredBar = $state<(typeof chartData)[0] | null>(null);
</script>

<ChartTheme title="Keywords by Tier" class={className}>
  <div class="tier-chart-container">
    <svg {width} {height} viewBox="0 0 {width} {height}" class="tier-chart-svg">
      <g transform="translate({margin.left}, {margin.top})">
        <!-- Grid lines -->
        {#each [0.25, 0.5, 0.75, 1] as tick}
          <line
            x1={xScale(maxCount * tick)}
            y1={0}
            x2={xScale(maxCount * tick)}
            y2={innerHeight}
            class="grid-line"
          />
        {/each}

        <!-- Bars -->
        {#each chartData as item, i}
          {@const barWidth = xScale(item.count)}
          {@const barY = yScale(item.label) ?? 0}
          {@const barHeight = yScale.bandwidth()}

          <!-- Background bar -->
          <rect
            x={0}
            y={barY}
            width={innerWidth}
            height={barHeight}
            fill="var(--color-bg-hover)"
            rx={4}
            class="bar-bg"
          />

          <!-- Data bar -->
          <rect
            x={0}
            y={barY}
            width={barWidth}
            height={barHeight}
            fill={item.color}
            rx={4}
            opacity={hoveredBar === item ? 1 : 0.85}
            class="bar-data"
            onmouseenter={() => (hoveredBar = item)}
            onmouseleave={() => (hoveredBar = null)}
            role="graphics-symbol"
            aria-label="{item.label}: {item.count} keywords"
          />

          <!-- Tier label -->
          <text
            x={-10}
            y={barY + barHeight / 2}
            class="tier-label"
            text-anchor="end"
            dominant-baseline="middle"
          >
            {item.label}
          </text>

          <!-- Count label -->
          <text
            x={barWidth + 8}
            y={barY + barHeight / 2}
            class="count-label"
            dominant-baseline="middle"
          >
            {item.count}
          </text>
        {/each}
      </g>
    </svg>

    <!-- Tooltip -->
    {#if hoveredBar}
      <div class="tier-tooltip">
        <div class="tooltip-header">
          <span class="tooltip-tier" style="background: {hoveredBar.color}"
            >Tier {hoveredBar.tier}</span
          >
          <span class="tooltip-label">{hoveredBar.label}</span>
        </div>
        <div class="tooltip-desc">{hoveredBar.description}</div>
        <div class="tooltip-stats">
          <span class="tooltip-count">{hoveredBar.count} keywords</span>
          <span class="tooltip-pct"
            >{hoveredBar.percentage.toFixed(1)}% of total</span
          >
        </div>
      </div>
    {/if}

    <!-- Summary stats -->
    <div class="tier-summary">
      <div class="summary-item">
        <span class="summary-value">{totalCount}</span>
        <span class="summary-label">Total Keywords</span>
      </div>
      <div class="summary-item highlight">
        <span class="summary-value">{tier0Count + tier1Count}</span>
        <span class="summary-label">High Priority</span>
      </div>
    </div>
  </div>
</ChartTheme>

<style>
  .tier-chart-container {
    position: relative;
    width: 100%;
    max-width: 550px;
    margin: 0 auto;
  }

  .tier-chart-svg {
    width: 100%;
    height: auto;
  }

  .grid-line {
    stroke: var(--color-border);
    stroke-dasharray: 2 4;
    opacity: 0.5;
  }

  .bar-bg {
    opacity: 0.3;
  }

  .bar-data {
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .bar-data:hover {
    filter: brightness(1.15);
  }

  .tier-label {
    font-family: var(--font-body);
    font-size: 12px;
    font-weight: 500;
    fill: var(--color-text-secondary);
  }

  .count-label {
    font-family: var(--font-mono);
    font-size: 12px;
    font-weight: 600;
    fill: var(--color-text-primary);
  }

  .tier-tooltip {
    position: absolute;
    top: 1rem;
    right: 1rem;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border-emphasis);
    border-radius: 8px;
    padding: 0.75rem 1rem;
    box-shadow: var(--shadow-lg);
    min-width: 180px;
    animation: tooltip-in 0.15s ease-out;
  }

  @keyframes tooltip-in {
    from {
      opacity: 0;
      transform: translateY(-4px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .tooltip-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.375rem;
  }

  .tooltip-tier {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 600;
    color: var(--color-bg-base);
    padding: 2px 6px;
    border-radius: 4px;
  }

  .tooltip-label {
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .tooltip-desc {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    margin-bottom: 0.5rem;
  }

  .tooltip-stats {
    display: flex;
    justify-content: space-between;
    font-size: 0.75rem;
  }

  .tooltip-count {
    font-weight: 600;
    color: var(--color-text-secondary);
  }

  .tooltip-pct {
    color: var(--color-text-muted);
  }

  .tier-summary {
    display: flex;
    justify-content: center;
    gap: 2rem;
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid var(--color-border);
  }

  .summary-item {
    text-align: center;
  }

  .summary-value {
    display: block;
    font-family: var(--font-display);
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--color-text-primary);
  }

  .summary-item.highlight .summary-value {
    color: var(--color-accent);
  }

  .summary-label {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
</style>
