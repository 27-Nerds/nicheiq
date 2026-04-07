<script lang="ts">
  import type { DetailedPainPoint } from "$lib/types/report";

  interface Props {
    painPoint: DetailedPainPoint;
    rank: number;
    isTop?: boolean;
    onViewOpportunity?: () => void;
  }

  let {
    painPoint,
    rank,
    isTop = false,
    onViewOpportunity,
  }: Props = $props();

  const severityLevel = $derived(
    painPoint.severity_score >= 0.7 ? 'critical'
    : painPoint.severity_score >= 0.5 ? 'high'
    : 'medium'
  );

  const severityLabel = $derived(
    severityLevel === 'critical' ? 'Critical'
    : severityLevel === 'high' ? 'High'
    : 'Medium'
  );

  const quotes = $derived(
    painPoint.representative_quotes?.slice(0, 2) ?? []
  );

  const segments = $derived(
    painPoint.affected_segments?.slice(0, 3) ?? []
  );
</script>

<article class="pp-card" class:pp-card--top={isTop}>
  <div class="pp-header">
    <div class="pp-rank" class:pp-rank--top={isTop}>{rank}</div>
    <div class="pp-title-col">
      {#if isTop}
        <span class="pp-top-flag">Top Opportunity</span>
      {/if}
      <h3 class="pp-title">{painPoint.title}</h3>
    </div>
    <span class="pp-sev pp-sev--{severityLevel}">
      {severityLabel}
    </span>
  </div>

  {#if painPoint.description}
    <p class="pp-body">{painPoint.description}</p>
  {/if}

  {#if segments.length > 0}
    <div class="pp-segments">
      {#each segments as segment}
        <span class="pp-segment">{segment}</span>
      {/each}
    </div>
  {/if}

  {#if quotes.length > 0 || painPoint.solution_approach}
    <details class="pp-evidence">
      <summary class="pp-evidence-trigger">Evidence & opportunity</summary>
      <div class="pp-evidence-body">
        {#if quotes.length > 0}
          {#each quotes as quote}
            <blockquote class="pp-quote">"{quote}"</blockquote>
          {/each}
        {/if}
        {#if painPoint.solution_approach}
          <div class="pp-opp">
            <strong>Opportunity:</strong> {painPoint.solution_approach}
          </div>
        {/if}
      </div>
    </details>
  {/if}

  <div class="pp-footer">
    <div class="pp-meta">
      {#if painPoint.categories?.length}
        {#each painPoint.categories.slice(0, 3) as cat}
          <span class="pp-tag">{cat}</span>
        {/each}
      {/if}
      <span class="pp-mentions">{painPoint.mention_count} mentions</span>
    </div>
    {#if onViewOpportunity}
      <button class="pp-action" onclick={onViewOpportunity}>
        Explore solutions
        <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 8h10M9 4l4 4-4 4"/></svg>
      </button>
    {/if}
  </div>
</article>

<style>
  /* ── Card shell ── */
  .pp-card {
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: 1.25rem 1.5rem;
    margin-bottom: 0.5rem;
  }

  .pp-card--top {
    border-color: var(--color-border-accent);
    background:
      linear-gradient(135deg, rgba(240, 96, 48, 0.05) 0%, transparent 50%),
      var(--color-bg-elevated);
  }

  /* ── Header: rank + title + severity ── */
  .pp-header {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    margin-bottom: 0.75rem;
  }

  .pp-rank {
    width: 2rem;
    height: 2rem;
    border-radius: var(--radius-sm);
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 0.875rem;
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
    background: var(--color-bg-surface);
    color: var(--color-text-muted);
  }

  .pp-rank--top {
    background: var(--color-accent);
    color: white;
  }

  .pp-title-col {
    flex: 1;
    min-width: 0;
  }

  .pp-top-flag {
    display: inline-block;
    font-size: 0.5625rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-accent);
    margin-bottom: 0.125rem;
  }

  .pp-title {
    font-family: var(--font-display);
    font-size: 0.9375rem;
    font-weight: 600;
    line-height: 1.4;
    color: var(--color-text-primary);
    margin: 0;
  }

  .pp-sev {
    display: inline-flex;
    align-items: center;
    font-size: 0.6875rem;
    font-weight: 600;
    padding: 0.25rem 0.625rem;
    border-radius: var(--radius-sm);
    flex-shrink: 0;
    white-space: nowrap;
    margin-top: 0.125rem;
  }

  .pp-sev--critical {
    background: var(--color-severity-critical-bg);
    color: var(--color-severity-critical);
  }

  .pp-sev--high {
    background: var(--color-severity-high-bg);
    color: var(--color-severity-high);
  }

  .pp-sev--medium {
    background: var(--color-severity-medium-bg);
    color: var(--color-severity-medium);
  }

  /* ── Body ── */
  .pp-body {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    line-height: 1.6;
    margin-bottom: 0.625rem;
  }

  /* ── Affected segments ── */
  .pp-segments {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
    margin-bottom: 0.75rem;
  }

  .pp-segment {
    font-size: 0.625rem;
    font-weight: 500;
    padding: 0.1875rem 0.5rem;
    border-radius: 9999px;
    background: var(--color-accent-subtle);
    color: var(--color-accent);
  }

  /* ── Evidence toggle ── */
  .pp-evidence {
    margin-bottom: 0.75rem;
  }

  .pp-evidence-trigger {
    list-style: none;
    cursor: pointer;
    font-family: var(--font-body);
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--color-accent);
    padding: 0.25rem 0;
    transition: color 150ms ease;
  }

  .pp-evidence-trigger::-webkit-details-marker { display: none; }
  .pp-evidence-trigger::marker { display: none; }

  .pp-evidence-trigger:hover {
    color: var(--color-accent-dark, #D9562A);
  }

  .pp-evidence-body {
    padding-top: 0.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .pp-quote {
    background: var(--color-bg-surface);
    border-left: 2px solid var(--color-border);
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
    padding: 0.625rem 0.875rem;
    font-size: 0.8125rem;
    font-style: italic;
    color: var(--color-text-secondary);
    line-height: 1.55;
    margin: 0;
  }

  .pp-opp {
    font-size: 0.8125rem;
    color: var(--color-opportunity);
    line-height: 1.5;
    padding: 0.5rem 0.75rem;
    background: var(--color-opportunity-bg);
    border-radius: var(--radius-sm);
  }

  .pp-opp strong {
    font-weight: 600;
  }

  /* ── Footer ── */
  .pp-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-top: 0.75rem;
    padding-top: 0.75rem;
  }

  .pp-meta {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .pp-tag {
    font-size: 0.625rem;
    font-weight: 500;
    padding: 0.1875rem 0.5rem;
    border-radius: 9999px;
    background: var(--color-bg-surface);
    color: var(--color-text-muted);
  }

  .pp-mentions {
    font-size: 0.625rem;
    font-weight: 600;
    color: var(--color-text-muted);
    font-variant-numeric: tabular-nums;
  }

  .pp-action {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    font-size: 0.75rem;
    font-weight: 600;
    color: white;
    background: var(--color-accent);
    border: none;
    padding: 0.375rem 0.75rem;
    border-radius: var(--radius-sm);
    cursor: pointer;
    transition: background-color 150ms ease;
  }

  .pp-action:hover {
    background: var(--color-accent-dark, #D9562A);
  }

  .pp-action:active {
    transform: scale(0.98);
  }

  .pp-action svg {
    transition: transform 0.15s ease;
  }

  .pp-action:hover svg {
    transform: translateX(2px);
  }
</style>
