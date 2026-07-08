<script lang="ts">
  interface Props {
    postsAnalyzed: number;
    subredditCount: number;
    totalEngagement: number;
    trend: { month: string; count: number }[];
    growthPct: number | null;
  }

  let {
    postsAnalyzed,
    subredditCount,
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
    return `${monthNames[parseInt(m, 10) - 1]} '${year.slice(2)}`;
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
        <span class="ms-growth-label">discussion growth</span>
      </div>
    {/if}

    <p class="ms-metrics">
      {postsAnalyzed} posts &middot; {subredditCount} subreddits{#if totalEngagement > 0} &middot; {formatEngagement(totalEngagement)} upvotes{/if}
    </p>
  </div>

  {#if showChart}
    <div class="ms-chart" role="img" aria-label="Monthly discussion trend">
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
              title="{formatMonth(point.month)}: {point.count} posts"
            ></div>
          {/each}
        </div>
      </div>
      <div class="ms-axis">
        <span>{firstMonth}</span>
        <span>{lastMonth}</span>
      </div>
    </div>
  {/if}
</div>

<style>
  .ms {
    display: flex;
    flex-direction: column;
    gap: 0.76rem;
  }

  .ms-header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 1rem;
  }

  .ms-growth {
    display: grid;
    gap: 0.04rem;
  }

  /* Color encodes the sign — rising discussion volume is a positive signal (green),
     falling is a caution (amber). Orange stays reserved for brand/interactive. */
  .ms-growth-value {
    font-family: var(--font-display);
    font-size: 1.5rem;
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
    font-size: 0.6875rem;
    font-weight: 600;
    color: var(--color-text-muted);
  }

  .ms-metrics {
    font-family: var(--font-body);
    font-size: 0.75rem;
    color: var(--color-text-secondary);
    margin: 0;
    font-variant-numeric: tabular-nums;
    text-align: right;
  }

  .ms-chart {
    padding: 0.62rem 0.68rem 0.48rem;
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 44%, transparent);
    border-radius: 0.75rem;
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
    font-size: 0.5625rem;
    color: var(--color-text-muted);
    font-variant-numeric: tabular-nums;
  }

  .ms-bars {
    display: flex;
    align-items: flex-end;
    gap: 3px;
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
    margin-top: 0.42rem;
  }

  .ms-axis span {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 500;
    color: var(--color-text-muted);
    letter-spacing: 0.02em;
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
</style>
