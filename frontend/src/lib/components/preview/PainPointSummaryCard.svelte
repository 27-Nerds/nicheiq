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

  const categories = $derived(painPoint.categories?.slice(0, 3) ?? []);
  const mentionLabel = $derived(
    `${painPoint.mention_count} ${painPoint.mention_count === 1 ? 'mention' : 'mentions'}`
  );
  const topQuote = $derived(quotes[0] ?? null);
</script>

<article class="pp-card" class:pp-card--lead={isTop}>
  <div class="pp-card__grid">
    <div class="pp-rank" class:pp-rank--lead={isTop}>{String(rank).padStart(2, '0')}</div>

    <div class="pp-main">
      <div class="pp-kicker-row">
        <span class="pp-kicker">{isTop ? 'Lead pain signal' : 'Pain cluster'}</span>
        <span class="pp-sev pp-sev--{severityLevel}">{severityLabel}</span>
      </div>
      <h3 class="pp-title">{painPoint.title}</h3>

      {#if painPoint.description}
        <p class="pp-body">{painPoint.description}</p>
      {/if}

      {#if isTop && topQuote}
        <blockquote class="pp-pullquote">"{topQuote}"</blockquote>
      {/if}

      <div class="pp-meta-row" aria-label="Pain point metadata">
        {#if segments.length > 0}
          <div class="pp-meta-group">
            <span class="pp-meta-label">Segments</span>
            <div class="pp-pills">
              {#each segments as segment}
                <span>{segment}</span>
              {/each}
            </div>
          </div>
        {/if}

        {#if categories.length > 0}
          <div class="pp-meta-group">
            <span class="pp-meta-label">Themes</span>
            <div class="pp-pills">
              {#each categories as cat}
                <span>{cat}</span>
              {/each}
            </div>
          </div>
        {/if}

        <div class="pp-meta-group pp-meta-group--count">
          <span class="pp-meta-label">Evidence</span>
          <strong>{mentionLabel}</strong>
        </div>
      </div>

      {#if isTop && (quotes.length > 1 || painPoint.solution_approach)}
        <details class="pp-evidence">
          <summary class="pp-evidence-trigger">Open supporting evidence</summary>
          <div class="pp-evidence-body">
            {#if quotes.length > 1}
              {#each quotes.slice(1) as quote}
                <blockquote class="pp-quote">"{quote}"</blockquote>
              {/each}
            {/if}
            {#if painPoint.solution_approach}
              <div class="pp-opp">
                <span>Opportunity lens</span>
                <p>{painPoint.solution_approach}</p>
              </div>
            {/if}
          </div>
        </details>
      {/if}
    </div>

    {#if onViewOpportunity && isTop}
      <button class="pp-action" onclick={onViewOpportunity}>
        <span>Explore matching ideas</span>
        <span class="pp-action-icon" aria-hidden="true">
          <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 8h10M9 4l4 4-4 4"/></svg>
        </span>
      </button>
    {/if}
  </div>
</article>

<style>
  .pp-card {
    position: relative;
    margin: 0;
    padding: 0.82rem 0;
    border-top: 1px solid color-mix(in srgb, var(--color-border-emphasis) 34%, transparent);
    background: transparent;
    transition:
      background-color 260ms cubic-bezier(0.32, 0.72, 0, 1),
      transform 260ms cubic-bezier(0.32, 0.72, 0, 1);
  }

  .pp-card:hover {
    transform: translateY(-1px);
  }

  .pp-card--lead {
    margin: 0.06rem 0 0.18rem;
    padding: 0.92rem;
    overflow: hidden;
    border: 1px solid color-mix(in srgb, var(--color-accent) 32%, var(--color-border-emphasis));
    border-radius: 0.82rem;
    background:
      linear-gradient(135deg, color-mix(in srgb, var(--color-accent) 5%, transparent), transparent 55%),
      color-mix(in srgb, var(--color-bg-elevated) 94%, white);
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.88),
      0 14px 32px rgba(234, 88, 12, 0.04);
  }

  .pp-card--lead:hover {
    transform: translateY(-2px);
  }

  .pp-card__grid {
    display: grid;
    grid-template-columns: 2.2rem minmax(0, 1fr) auto;
    align-items: flex-start;
    gap: 0.74rem;
  }

  .pp-rank {
    width: 1.9rem;
    height: 1.9rem;
    border-radius: 0.52rem;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: var(--font-display);
    font-weight: 760;
    font-size: 0.68rem;
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
    background: color-mix(in srgb, var(--color-bg-surface) 82%, white);
    color: var(--color-text-muted);
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 32%, transparent);
  }

  .pp-rank--lead {
    background: var(--color-accent);
    color: white;
    border-color: transparent;
    box-shadow: 0 8px 18px rgba(234, 88, 12, 0.12);
  }

  .pp-main {
    min-width: 0;
  }

  .pp-kicker-row {
    display: flex;
    align-items: center;
    gap: 0.44rem;
    margin-bottom: 0.24rem;
  }

  .pp-kicker,
  .pp-meta-label,
  .pp-opp span {
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: 0.56rem;
    font-weight: 760;
    letter-spacing: 0.06em;
    line-height: 1;
    text-transform: uppercase;
  }

  .pp-card--lead .pp-kicker {
    color: var(--color-accent);
  }

  .pp-title {
    font-family: var(--font-display);
    font-size: 0.86rem;
    font-weight: 760;
    line-height: 1.2;
    color: var(--color-text-primary);
    margin: 0;
    text-wrap: balance;
  }

  .pp-card--lead .pp-title {
    max-width: 54rem;
    font-size: 0.96rem;
  }

  .pp-sev {
    display: inline-flex;
    align-items: center;
    font-size: 0.66rem;
    font-weight: 600;
    padding: 0.2rem 0.52rem;
    border-radius: 0.38rem;
    flex-shrink: 0;
    white-space: nowrap;
    border: 1px solid transparent;
  }

  .pp-sev--critical,
  .pp-sev--high {
    background: color-mix(in srgb, var(--color-severity-critical-bg) 72%, var(--color-bg-elevated));
    color: var(--color-severity-critical);
    border-color: color-mix(in srgb, var(--color-severity-critical) 16%, transparent);
  }

  .pp-sev--medium {
    background: color-mix(in srgb, var(--color-bg-surface) 72%, white);
    color: var(--color-text-muted);
    border-color: color-mix(in srgb, var(--color-border-emphasis) 28%, transparent);
  }

  .pp-body {
    max-width: 90ch;
    font-size: 0.74rem;
    color: var(--color-text-secondary);
    line-height: 1.48;
    margin: 0.26rem 0 0;
    text-wrap: pretty;
  }

  .pp-card--lead .pp-body {
    font-size: 0.78rem;
  }

  .pp-pullquote {
    margin: 0.64rem 0 0;
    padding: 0.52rem 0.66rem;
    border-left: 2px solid color-mix(in srgb, var(--color-accent) 34%, transparent);
    border-radius: 0 0.46rem 0.46rem 0;
    background: color-mix(in srgb, var(--color-accent) 3%, white);
    color: var(--color-text-secondary);
    font-size: 0.72rem;
    line-height: 1.48;
    text-wrap: pretty;
  }

  .pp-meta-row {
    display: flex;
    align-items: flex-end;
    gap: 0.56rem 0.86rem;
    flex-wrap: wrap;
    margin-top: 0.58rem;
  }

  .pp-meta-group {
    display: grid;
    gap: 0.26rem;
    min-width: 0;
  }

  .pp-meta-group--count strong {
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: 0.66rem;
    font-weight: 760;
    line-height: 1.15;
    font-variant-numeric: tabular-nums;
  }

  .pp-pills {
    display: flex;
    flex-wrap: wrap;
    gap: 0.28rem;
  }

  .pp-pills span {
    max-width: 22rem;
    padding: 0.15rem 0.46rem;
    overflow: hidden;
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 34%, transparent);
    border-radius: 999px;
    background: color-mix(in srgb, var(--color-bg-surface) 78%, white);
    color: var(--color-text-muted);
    font-size: 0.6rem;
    font-weight: 650;
    line-height: 1.2;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .pp-evidence {
    margin-top: 0.64rem;
  }

  .pp-evidence-trigger {
    list-style: none;
    cursor: pointer;
    font-family: var(--font-body);
    font-size: 0.68rem;
    font-weight: 650;
    color: var(--color-text-secondary);
    padding: 0.12rem 0;
    transition: color 220ms cubic-bezier(0.32, 0.72, 0, 1);
    display: inline-flex;
    align-items: center;
    gap: 0.35em;
  }

  .pp-evidence-trigger::before {
    content: '▸';
    display: inline-block;
    font-size: 0.85em;
    transition: transform 240ms cubic-bezier(0.32, 0.72, 0, 1);
  }

  .pp-evidence[open] .pp-evidence-trigger::before {
    transform: rotate(90deg);
  }

  .pp-evidence-trigger::-webkit-details-marker { display: none; }
  .pp-evidence-trigger::marker { display: none; }

  .pp-evidence-trigger:hover {
    color: var(--color-accent);
  }

  .pp-evidence-body {
    padding-top: 0.54rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .pp-quote {
    background: color-mix(in srgb, var(--color-bg-surface) 76%, white);
    border-left: 2px solid color-mix(in srgb, var(--color-border-emphasis) 48%, transparent);
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
    padding: 0.52rem 0.68rem;
    font-size: 0.74rem;
    font-style: italic;
    color: var(--color-text-secondary);
    line-height: 1.55;
    margin: 0;
  }

  .pp-opp {
    display: grid;
    gap: 0.22rem;
    padding: 0.54rem 0.62rem;
    border: 1px solid color-mix(in srgb, var(--color-accent) 18%, transparent);
    border-radius: 0.52rem;
    background: color-mix(in srgb, var(--color-opportunity-bg) 58%, white);
  }

  .pp-opp p {
    margin: 0;
    color: var(--color-opportunity);
    font-size: 0.72rem;
    line-height: 1.46;
    text-wrap: pretty;
  }

  .pp-action {
    display: inline-flex;
    align-items: center;
    gap: 0.42rem;
    font-size: 0.7rem;
    font-weight: 720;
    color: var(--color-accent);
    background: color-mix(in srgb, var(--color-bg-elevated) 88%, transparent);
    border: 1px solid color-mix(in srgb, var(--color-accent) 22%, transparent);
    padding: 0.28rem 0.34rem 0.28rem 0.58rem;
    border-radius: 999px;
    cursor: pointer;
    transition:
      color 220ms cubic-bezier(0.32, 0.72, 0, 1),
      border-color 220ms cubic-bezier(0.32, 0.72, 0, 1),
      background-color 220ms cubic-bezier(0.32, 0.72, 0, 1),
      transform 220ms cubic-bezier(0.32, 0.72, 0, 1);
  }

  .pp-action:hover {
    color: var(--color-accent-dark, #D9562A);
    border-color: color-mix(in srgb, var(--color-accent) 26%, transparent);
    background: color-mix(in srgb, var(--color-accent) 7%, var(--color-bg-elevated));
  }

  .pp-action:active {
    transform: scale(0.98);
  }

  .pp-action-icon {
    display: inline-flex;
    width: 1.14rem;
    height: 1.14rem;
    align-items: center;
    justify-content: center;
    border-radius: 999px;
    background: color-mix(in srgb, var(--color-accent) 11%, transparent);
    transition:
      transform 240ms cubic-bezier(0.32, 0.72, 0, 1),
      background-color 240ms cubic-bezier(0.32, 0.72, 0, 1);
  }

  .pp-action:hover .pp-action-icon {
    transform: translateX(2px);
    background: color-mix(in srgb, var(--color-accent) 16%, transparent);
  }

  @media (max-width: 760px) {
    .pp-card__grid {
      grid-template-columns: 1.95rem minmax(0, 1fr);
    }

    .pp-action {
      grid-column: 2;
      justify-self: start;
      margin-top: 0.64rem;
    }

    .pp-pills span {
      max-width: 100%;
      white-space: normal;
    }
  }
</style>
