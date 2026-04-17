<script lang="ts">
  import { scaleLinear } from "d3-scale";
  import ChartTheme from "./ChartTheme.svelte";
  import Tooltip from "$lib/components/ui/Tooltip.svelte";
  import type { DetailedPainPoint } from "$lib/types/report";
  import { formatScorePercent } from "$lib/utils/format";

  interface Props {
    painPoints: DetailedPainPoint[];
    class?: string;
  }

  let { painPoints, class: className = "" }: Props = $props();

  // Chart dimensions
  const width = 500;
  const height = 500;
  const margin = { top: 40, right: 30, bottom: 50, left: 60 };
  const innerWidth = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;

  // Scales
  const xScale = scaleLinear().domain([0, 1]).range([0, innerWidth]);
  const yScale = scaleLinear().domain([0, 1]).range([innerHeight, 0]);

  // Map pain points to chart data
  const chartData = $derived(
    painPoints.map((p, i) => ({
      id: i,
      x: p.willingness_to_pay,
      y: p.severity_score,
      r: Math.max(8, Math.min(24, (p.mention_count || 1) * 3)),
      title: p.title,
      description: p.description,
      opportunity: p.opportunity_level,
      mentionCount: p.mention_count,
      platforms: p.source_platforms,
    })),
  );

  // Check if all WTP values are same (clustering issue)
  const allSameWTP = $derived(
    chartData.length > 1 && chartData.every((p) => p.x === chartData[0]?.x),
  );

  // Get X position with spread when all WTP values are identical
  function getSpreadX(point: (typeof chartData)[0], index: number): number {
    if (!allSameWTP) return point.x;
    // Spread points evenly across a range (avoid false correlation with severity)
    const spreadRange = 0.4; // 40% of x-axis width
    const spreadStart = 0.05; // Start slightly from left edge
    const spreadStep =
      chartData.length > 1 ? spreadRange / (chartData.length - 1) : 0;
    return spreadStart + index * spreadStep;
  }

  // Get color based on opportunity level
  function getColor(opportunity: string): string {
    switch (opportunity) {
      case "high":
        return "var(--color-success)";
      case "medium":
        return "var(--color-accent)";
      default:
        return "var(--color-text-muted)";
    }
  }

  // Hover state
  let hoveredPoint = $state<(typeof chartData)[0] | null>(null);
  let mousePos = $state({ x: 0, y: 0 });

  function handleMouseEnter(point: (typeof chartData)[0], event: MouseEvent) {
    hoveredPoint = point;
    const rect = (event.currentTarget as SVGElement)
      .closest("svg")
      ?.getBoundingClientRect();
    if (rect) {
      mousePos = {
        x: event.clientX - rect.left,
        y: event.clientY - rect.top,
      };
    }
  }

  function handleMouseLeave() {
    hoveredPoint = null;
  }
</script>

<ChartTheme title="Pain Point Opportunity Matrix" class={className}>
  <div class="matrix-container">
    <svg {width} {height} viewBox="0 0 {width} {height}" class="matrix-svg">
      <defs>
        <!-- Glow filter for high opportunity points -->
        <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="3" result="coloredBlur" />
          <feMerge>
            <feMergeNode in="coloredBlur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      <g transform="translate({margin.left}, {margin.top})">
        <!-- Quadrant backgrounds -->
        <rect
          x={innerWidth / 2}
          y={0}
          width={innerWidth / 2}
          height={innerHeight / 2}
          fill="var(--color-accent-subtle)"
          class="quadrant"
        />
        <rect
          x={0}
          y={0}
          width={innerWidth / 2}
          height={innerHeight / 2}
          fill="var(--quadrant-high-low)"
          class="quadrant"
        />
        <rect
          x={innerWidth / 2}
          y={innerHeight / 2}
          width={innerWidth / 2}
          height={innerHeight / 2}
          fill="var(--quadrant-low-high)"
          class="quadrant"
        />
        <rect
          x={0}
          y={innerHeight / 2}
          width={innerWidth / 2}
          height={innerHeight / 2}
          fill="var(--quadrant-low-low)"
          class="quadrant"
        />

        <!-- Quadrant labels -->
        <text x={innerWidth * 0.75} y={20} class="quadrant-label success"
          >Best Opportunity</text
        >
        <text x={innerWidth * 0.25} y={20} class="quadrant-label error"
          >Validation Risk</text
        >
        <text
          x={innerWidth * 0.75}
          y={innerHeight - 10}
          class="quadrant-label info">Nice to Have</text
        >
        <text
          x={innerWidth * 0.25}
          y={innerHeight - 10}
          class="quadrant-label muted">Deprioritize</text
        >

        <!-- Grid lines -->
        <line
          x1={innerWidth / 2}
          y1={0}
          x2={innerWidth / 2}
          y2={innerHeight}
          class="grid-line"
        />
        <line
          x1={0}
          y1={innerHeight / 2}
          x2={innerWidth}
          y2={innerHeight / 2}
          class="grid-line"
        />

        <!-- Axis lines -->
        <line
          x1={0}
          y1={innerHeight}
          x2={innerWidth}
          y2={innerHeight}
          class="axis-line"
        />
        <line x1={0} y1={0} x2={0} y2={innerHeight} class="axis-line" />

        <!-- X-axis labels -->
        <text x={0} y={innerHeight + 25} class="axis-tick">0%</text>
        <text x={innerWidth / 2} y={innerHeight + 25} class="axis-tick"
          >50%</text
        >
        <text x={innerWidth} y={innerHeight + 25} class="axis-tick">100%</text>
        <text x={innerWidth / 2} y={innerHeight + 42} class="axis-label"
          >Willingness to Pay</text
        >

        <!-- Y-axis labels -->
        <text x={-15} y={innerHeight} class="axis-tick" text-anchor="end"
          >0%</text
        >
        <text x={-15} y={innerHeight / 2} class="axis-tick" text-anchor="end"
          >50%</text
        >
        <text x={-15} y={5} class="axis-tick" text-anchor="end">100%</text>
        <text
          x={-40}
          y={innerHeight / 2}
          class="axis-label"
          transform="rotate(-90, -40, {innerHeight / 2})"
        >
          Severity Score
        </text>

        <!-- Data points -->
        {#each chartData as point, index}
          <circle
            cx={xScale(getSpreadX(point, index))}
            cy={yScale(point.y)}
            r={hoveredPoint === point ? point.r * 1.2 : point.r}
            fill={getColor(point.opportunity)}
            opacity={hoveredPoint === point ? 1 : 0.75}
            class="data-point"
            class:highlighted={point.opportunity === "high"}
            filter={point.opportunity === "high" ? "url(#glow)" : undefined}
            onmouseenter={(e) => handleMouseEnter(point, e)}
            onmouseleave={handleMouseLeave}
            role="button"
            tabindex="0"
            aria-label="{point.title}: Severity {formatScorePercent(
              point.y,
            )}, WTP {formatScorePercent(point.x)}"
          />
        {/each}
      </g>
    </svg>

    <!-- Custom tooltip -->
    {#if hoveredPoint}
      <div
        class="chart-tooltip"
        style="left: {mousePos.x + 15}px; top: {mousePos.y - 10}px;"
      >
        <div class="tooltip-title">{hoveredPoint.title}</div>
        <div class="tooltip-stats">
          <span
            >Severity: <strong>{formatScorePercent(hoveredPoint.y)}</strong
            ></span
          >
          <span>WTP: <strong>{formatScorePercent(hoveredPoint.x)}</strong></span
          >
        </div>
        <div class="tooltip-meta">
          <span class="tooltip-mentions"
            >{hoveredPoint.mentionCount} {hoveredPoint.mentionCount === 1 ? 'mention' : 'mentions'}</span
          >
          <span
            class="tooltip-opportunity opportunity-{hoveredPoint.opportunity}"
          >
            {hoveredPoint.opportunity} opportunity
          </span>
        </div>
      </div>
    {/if}

    <!-- Legend -->
    <div class="matrix-legend">
      <div class="legend-item">
        <span class="legend-dot" style="background: var(--color-success)"
        ></span>
        <span>High Opportunity</span>
      </div>
      <div class="legend-item">
        <span class="legend-dot" style="background: var(--color-accent)"></span>
        <span>Medium Opportunity</span>
      </div>
      <div class="legend-item">
        <span class="legend-dot" style="background: var(--color-text-muted)"
        ></span>
        <span>Low Opportunity</span>
      </div>
    </div>
  </div>
</ChartTheme>

<style>
  .matrix-container {
    position: relative;
    width: 100%;
    max-width: 550px;
    margin: 0 auto;
  }

  .matrix-svg {
    width: 100%;
    height: auto;
  }

  .quadrant {
    transition: opacity 0.2s ease;
  }

  .quadrant-label {
    font-family: var(--font-mono);
    font-size: 10px;
    font-weight: 500;
    text-anchor: middle;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .quadrant-label.success {
    fill: var(--color-success);
  }

  .quadrant-label.error {
    fill: var(--color-error);
    opacity: 0.7;
  }

  .quadrant-label.info {
    fill: var(--viz-cat-2);
    opacity: 0.7;
  }

  .quadrant-label.muted {
    fill: var(--color-text-muted);
    opacity: 0.5;
  }

  .grid-line {
    stroke: var(--color-border);
    stroke-dasharray: 4 4;
  }

  .axis-line {
    stroke: var(--color-border-emphasis);
  }

  .axis-tick {
    font-family: var(--font-mono);
    font-size: 10px;
    fill: var(--color-text-muted);
    text-anchor: middle;
  }

  .axis-label {
    font-family: var(--font-body);
    font-size: 11px;
    fill: var(--color-text-secondary);
    text-anchor: middle;
  }

  .data-point {
    cursor: pointer;
    transition:
      r 0.15s ease,
      opacity 0.15s ease;
  }

  .data-point.highlighted {
    animation: pulse-subtle 2s ease-in-out infinite;
  }

  @keyframes pulse-subtle {
    0%,
    100% {
      opacity: 0.75;
    }
    50% {
      opacity: 1;
    }
  }

  .chart-tooltip {
    position: absolute;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border-emphasis);
    border-radius: 8px;
    padding: 0.75rem 1rem;
    box-shadow: var(--shadow-lg);
    pointer-events: none;
    z-index: 100;
    max-width: 250px;
    animation: tooltip-in 0.15s ease-out;
  }

  @keyframes tooltip-in {
    from {
      opacity: 0;
      transform: translateY(4px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .tooltip-title {
    font-family: var(--font-body);
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin-bottom: 0.5rem;
    line-height: 1.3;
  }

  .tooltip-stats {
    display: flex;
    gap: 1rem;
    font-size: 0.75rem;
    color: var(--color-text-secondary);
    margin-bottom: 0.5rem;
  }

  .tooltip-stats strong {
    color: var(--color-text-primary);
  }

  .tooltip-meta {
    display: flex;
    justify-content: space-between;
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }

  .tooltip-opportunity {
    text-transform: capitalize;
  }

  .tooltip-opportunity.opportunity-high {
    color: var(--color-success);
  }

  .tooltip-opportunity.opportunity-medium {
    color: var(--color-accent);
  }

  .matrix-legend {
    display: flex;
    justify-content: center;
    gap: 1.5rem;
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid var(--color-border);
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.75rem;
    color: var(--color-text-muted);
  }

  .legend-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
  }
</style>
