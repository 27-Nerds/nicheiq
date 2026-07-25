<script lang="ts">
  interface Props {
    discussionsAnalyzed: number;
    communityCount: number;
    totalEngagement: number;
    trend: { month: string; count: number }[];
    growthPct: number | null;
  }

  let {
    discussionsAnalyzed,
    communityCount,
    totalEngagement,
    trend,
    growthPct,
  }: Props = $props();

  const maxCount = $derived(Math.max(...trend.map(t => t.count), 1));
  const totalTrendPosts = $derived(trend.reduce((sum, t) => sum + t.count, 0));
  const showChart = $derived(totalTrendPosts >= 5);

  function formatMonth(month: string): string {
    const [year, m] = month.split('-');
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const name = monthNames[parseInt(m, 10) - 1];
    return name && year ? `${name} '${year.slice(2)}` : month;
  }

  function formatEngagement(n: number): string {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
    return n.toString();
  }

  const firstMonth = $derived(trend.length > 0 ? formatMonth(trend[0].month) : '');
  const lastMonth = $derived(trend.length > 0 ? formatMonth(trend[trend.length - 1].month) : '');
</script>

<div class="ms">
  <div class="ms-header">
    {#if growthPct !== null}
      <div class="ms-growth">
        <span class="ms-growth-value" class:is-negative={growthPct < 0}>
          {growthPct >= 0 ? '\u2191' : '\u2193'} {Math.abs(growthPct)}%
        </span>
        <span class="ms-growth-label">discussion volume</span>
        <span class="ms-growth-period">Recent 6 months vs previous 6</span>
      </div>
    {/if}

    <p class="ms-metrics">
      {discussionsAnalyzed.toLocaleString()} discussions &middot;
      {communityCount.toLocaleString()} communities{#if totalEngagement > 0}
        &middot; {formatEngagement(totalEngagement)} engagement signals
      {/if}
    </p>
  </div>

  {#if showChart}
    <div
      class="ms-chart"
      role="img"
      aria-label={`Monthly captured discussion counts from ${firstMonth} to ${lastMonth}. Highest month: ${maxCount} discussions.`}
    >
      <div class="ms-plot">
        <div class="ms-gridlines" aria-hidden="true">
          <span class="ms-gridline ms-gridline--top">
            <span class="ms-gridline-label">{maxCount}</span>
          </span>
          <span class="ms-gridline ms-gridline--mid">
            <span class="ms-gridline-label">{Math.round(maxCount / 2)}</span>
          </span>
          <span class="ms-gridline ms-gridline--bot"></span>
        </div>
        <div class="ms-bars">
          {#each trend as point, i}
            {@const pct = maxCount > 0 ? (point.count / maxCount * 100) : 0}
            {@const intensity = trend.length > 1 ? (i / (trend.length - 1)) : 1}
            <div
              class="ms-bar"
              class:ms-bar--zero={point.count === 0}
              style="height: {point.count > 0 ? `${Math.max(pct, 3)}%` : '2px'}; --bar-mix: {Math.round(30 + intensity * 70)}%; animation-delay: {i * 25}ms"
              title="{formatMonth(point.month)}: {point.count} discussions"
            ></div>
          {/each}
        </div>
      </div>
      <div class="ms-axis">
        <span>{firstMonth}</span>
        <span>{lastMonth}</span>
      </div>
    </div>
    <details class="ms-data">
      <summary>View monthly discussion counts</summary>
      <div class="ms-data-scroll">
        <table>
          <caption class="sr-only">Captured discussion counts by month</caption>
          <thead>
            <tr><th scope="col">Month</th><th scope="col">Discussions</th></tr>
          </thead>
          <tbody>
            {#each trend as point}
              <tr><th scope="row">{formatMonth(point.month)}</th><td>{point.count}</td></tr>
            {/each}
          </tbody>
        </table>
      </div>
    </details>
  {:else if trend.length > 0}
    <p class="ms-empty">Not enough dated discussions to show a reliable monthly trend.</p>
  {/if}
</div>

<style>
  .ms {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .ms-header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: var(--space-4);
  }

  .ms-growth {
    display: grid;
    gap: var(--space-1);
  }

  /* Color encodes the sign — rising discussion volume is a positive signal (green),
     falling is a caution (amber). Orange stays reserved for brand/interactive. */
  .ms-growth-value {
    font-family: var(--font-display);
    font-size: var(--text-2xl);
    font-weight: 800;
    color: var(--color-success-dark);
    font-variant-numeric: tabular-nums;
    line-height: 0.98;
  }
  .ms-growth-value.is-negative {
    color: var(--color-warning-dark);
  }

  .ms-growth-label {
    font-family: var(--font-body);
    font-size: var(--text-11);
    font-weight: 600;
    color: var(--color-text-muted);
  }

  .ms-growth-period {
    color: var(--color-text-muted);
    font-size: var(--text-11);
    line-height: var(--leading-snug);
  }

  .ms-metrics {
    font-family: var(--font-body);
    font-size: var(--text-sm);
    color: var(--color-text-secondary);
    margin: 0;
    font-variant-numeric: tabular-nums;
    text-align: right;
  }

  .ms-chart {
    padding: var(--space-3) var(--space-3) var(--space-2);
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 44%, transparent);
    border-radius: var(--radius-lg);
    background:
      color-mix(in srgb, var(--color-bg-surface) 72%, transparent);
  }

  .ms-plot {
    position: relative;
    height: 68px;
    padding-right: 1.75rem;
  }

  .ms-gridlines {
    position: absolute;
    inset: 0 1.75rem 0 0;
    pointer-events: none;
  }

  .ms-gridline {
    position: absolute;
    left: 0;
    right: 0;
    height: 1px;
    background: color-mix(in srgb, var(--color-border) 68%, transparent);
  }

  .ms-gridline--top { top: 0; }
  .ms-gridline--mid { top: 50%; }
  .ms-gridline--bot { bottom: 0; }

  .ms-gridline-label {
    position: absolute;
    left: 100%;
    margin-left: 0.25rem;
    top: -0.5em;
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--color-text-secondary);
    font-variant-numeric: tabular-nums;
  }

  .ms-bars {
    display: flex;
    align-items: flex-end;
    gap: var(--space-1);
    height: 100%;
    position: relative;
  }

  .ms-bar {
    flex: 1;
    background: color-mix(in srgb, var(--color-accent) var(--bar-mix, 100%), var(--color-bg-surface));
    border-radius: 4px 4px 1px 1px;
    transform-origin: bottom;
    animation: barGrow 420ms var(--ease-data-viz, cubic-bezier(0.32, 0.72, 0, 1)) backwards;
    min-width: 0;
  }

  .ms-bar--zero {
    background: var(--color-border);
    border-radius: 0;
  }

  @keyframes barGrow {
    from { transform: scaleY(0); }
    to { transform: scaleY(1); }
  }

  .ms-axis {
    display: flex;
    justify-content: space-between;
    margin-top: var(--space-1-5);
  }

  .ms-axis span {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 500;
    color: var(--color-text-muted);
    letter-spacing: 0.02em;
  }

  .ms-data {
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
  }

  .ms-data summary {
    width: fit-content;
    cursor: pointer;
    font-weight: 600;
  }

  .ms-data-scroll {
    max-width: 28rem;
    margin-top: var(--space-2);
    overflow-x: auto;
  }

  .ms-data table {
    width: 100%;
    border-collapse: collapse;
  }

  .ms-data th,
  .ms-data td {
    padding: var(--space-2);
    border-bottom: 1px solid var(--color-border);
    text-align: left;
    font-variant-numeric: tabular-nums;
  }

  .ms-data td {
    text-align: right;
  }

  .ms-empty {
    margin: 0;
    padding: var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    color: var(--color-text-secondary);
    font-size: var(--text-13);
  }

  @media (max-width: 640px) {
    .ms-header {
      display: grid;
      align-items: start;
    }

    .ms-metrics {
      text-align: left;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .ms-bar {
      animation: none;
    }
  }
</style>
