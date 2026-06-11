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
  {#if growthPct !== null}
    <div class="ms-growth">
      <span class="ms-growth-value">
        {growthPct >= 0 ? '\u2191' : '\u2193'} {Math.abs(growthPct)}%
      </span>
      <span class="ms-growth-label">discussion growth</span>
    </div>
  {/if}

  <p class="ms-metrics">
    {postsAnalyzed} posts &middot; {subredditCount} subreddits{#if totalEngagement > 0} &middot; {formatEngagement(totalEngagement)} upvotes{/if}
  </p>

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
    gap: 0.625rem;
  }

  /* ── Growth hero ── */
  .ms-growth {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
  }

  .ms-growth-value {
    font-family: var(--font-display);
    font-size: 1.875rem;
    font-weight: 700;
    color: var(--color-accent);
    font-variant-numeric: tabular-nums;
    line-height: 1.1;
  }

  .ms-growth-label {
    font-family: var(--font-body);
    font-size: 0.8125rem;
    color: var(--color-text-muted);
  }

  /* ── Inline metrics ── */
  .ms-metrics {
    font-family: var(--font-body);
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    margin: 0;
    font-variant-numeric: tabular-nums;
  }

  /* ── Bar chart ── */
  .ms-chart {
    margin-top: 0.25rem;
  }

  .ms-plot {
    position: relative;
    height: 80px;
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
    background: var(--color-border);
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
    gap: 2px;
    height: 100%;
    position: relative;
  }

  .ms-bar {
    flex: 1;
    background: color-mix(in srgb, var(--color-accent) var(--bar-mix, 100%), var(--color-bg-surface));
    border-radius: 2px 2px 0 0;
    transform-origin: bottom;
    animation: barGrow 300ms var(--ease-data-viz, cubic-bezier(0.4, 0, 0.2, 1)) backwards;
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
    margin-top: 0.375rem;
  }

  .ms-axis span {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 500;
    color: var(--color-text-muted);
    letter-spacing: 0.02em;
  }
</style>
