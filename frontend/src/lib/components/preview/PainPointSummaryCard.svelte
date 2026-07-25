<script lang="ts">
  import type { DetailedPainPoint } from "$lib/types/report";
  import { cleanEvidenceExcerpt } from "$lib/utils/cleanEvidenceExcerpt";

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
    painPoint.severity_score >= 0.7 ? 'high'
    : painPoint.severity_score >= 0.4 ? 'medium'
    : 'low'
  );

  const severityLabel = $derived(
    severityLevel === 'high' ? 'High'
    : severityLevel === 'medium' ? 'Medium'
    : 'Low'
  );

  const quotes = $derived(
    (painPoint.representative_quotes ?? [])
      .map(cleanEvidenceExcerpt)
      .filter((quote) => quote.length > 0)
      .slice(0, 3)
  );

  const segments = $derived(
    painPoint.affected_segments?.slice(0, 3) ?? []
  );

  const categories = $derived(painPoint.categories?.slice(0, 3) ?? []);
  const mentionLabel = $derived(
    `${painPoint.mention_count} ${painPoint.mention_count === 1 ? 'mention' : 'mentions'}`
  );
  const topQuote = $derived(quotes[0] ?? null);
  const detailQuotes = $derived(isTop ? quotes.slice(1) : quotes);
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

      {#if detailQuotes.length > 0 || painPoint.solution_approach}
        <details class="pp-evidence">
          <summary class="pp-evidence-trigger">
            {detailQuotes.length > 0
              ? `View ${detailQuotes.length} ${detailQuotes.length === 1 ? "evidence excerpt" : "evidence excerpts"}`
              : "View opportunity lens"}
          </summary>
          <div class="pp-evidence-body">
            {#if detailQuotes.length > 0}
              {#each detailQuotes as quote}
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
        <span>Review ranked ideas</span>
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
    padding: var(--space-3) 0;
    border-top: 1px solid color-mix(in srgb, var(--color-border-emphasis) 34%, transparent);
    background: transparent;
    transition:
      background-color var(--duration-normal) var(--ease-default),
      transform var(--duration-normal) var(--ease-default);
  }

  .pp-card:hover {
    transform: translateY(-1px);
  }

  .pp-card--lead {
    margin: 0 0 var(--space-1);
    padding: var(--space-4);
    overflow: hidden;
    border: 1px solid color-mix(in srgb, var(--color-accent) 32%, var(--color-border-emphasis));
    border-radius: var(--radius-lg);
    background: color-mix(in srgb, var(--color-accent) 4%, var(--color-bg-elevated));
  }

  .pp-card--lead:hover {
    transform: translateY(-2px);
  }

  .pp-card__grid {
    display: grid;
    grid-template-columns: var(--space-8) minmax(0, 1fr) auto;
    align-items: flex-start;
    gap: var(--space-3);
  }

  .pp-rank {
    width: var(--space-8);
    height: var(--space-8);
    border-radius: var(--radius-md);
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: var(--font-display);
    font-weight: 700;
    font-size: var(--text-11);
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
    background: color-mix(in srgb, var(--color-bg-surface) 82%, var(--color-bg-elevated));
    color: var(--color-text-muted);
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 32%, transparent);
  }

  .pp-rank--lead {
    background: var(--color-accent-dark);
    color: var(--color-text-on-accent);
    border-color: transparent;
  }

  .pp-main {
    min-width: 0;
  }

  .pp-kicker-row {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-1);
  }

  .pp-kicker,
  .pp-meta-label,
  .pp-opp span {
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.07em;
    line-height: 1;
    text-transform: uppercase;
  }

  .pp-card--lead .pp-kicker {
    color: var(--color-accent-dark);
  }

  .pp-title {
    font-family: var(--font-display);
    font-size: var(--text-base);
    font-weight: 700;
    line-height: 1.2;
    color: var(--color-text-primary);
    margin: 0;
    text-wrap: balance;
  }

  .pp-card--lead .pp-title {
    max-width: 54rem;
    font-size: var(--text-md);
  }

  .pp-sev {
    display: inline-flex;
    align-items: center;
    font-size: var(--text-xs);
    font-weight: 600;
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
    flex-shrink: 0;
    white-space: nowrap;
    border: 1px solid transparent;
  }

  .pp-sev--high {
    background: color-mix(in srgb, var(--color-severity-critical-bg) 72%, var(--color-bg-elevated));
    color: var(--color-error-text);
    border-color: color-mix(in srgb, var(--color-severity-critical) 16%, transparent);
  }

  .pp-sev--medium {
    background: var(--color-warning-subtle);
    color: var(--color-warning-dark);
    border-color: color-mix(in srgb, var(--color-warning) 24%, transparent);
  }

  .pp-sev--low {
    background: color-mix(in srgb, var(--color-bg-surface) 72%, var(--color-bg-elevated));
    color: var(--color-text-muted);
    border-color: color-mix(in srgb, var(--color-border-emphasis) 28%, transparent);
  }

  .pp-body {
    max-width: 90ch;
    font-size: var(--text-sm);
    color: var(--color-text-secondary);
    line-height: 1.48;
    margin: var(--space-1) 0 0;
    text-wrap: pretty;
  }

  .pp-card--lead .pp-body {
    font-size: var(--text-13);
  }

  .pp-pullquote {
    margin: var(--space-3) 0 0;
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-bg-surface);
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: 1.48;
    text-wrap: pretty;
  }

  .pp-meta-row {
    display: flex;
    align-items: flex-end;
    gap: var(--space-2) var(--space-4);
    flex-wrap: wrap;
    margin-top: var(--space-2);
  }

  .pp-meta-group {
    display: grid;
    gap: var(--space-1);
    min-width: 0;
  }

  .pp-meta-group--count strong {
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    line-height: 1.15;
    font-variant-numeric: tabular-nums;
  }

  .pp-pills {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
  }

  .pp-pills span {
    max-width: 22rem;
    padding: var(--space-1) var(--space-2);
    overflow: hidden;
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 34%, transparent);
    border-radius: var(--radius-full);
    background: color-mix(in srgb, var(--color-bg-surface) 78%, var(--color-bg-elevated));
    color: var(--color-text-muted);
    font-size: var(--text-xs);
    font-weight: 600;
    line-height: 1.2;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .pp-evidence {
    margin-top: var(--space-3);
  }

  .pp-evidence-trigger {
    list-style: none;
    cursor: pointer;
    font-family: var(--font-body);
    font-size: var(--text-11);
    font-weight: 600;
    color: var(--color-text-secondary);
    padding: var(--space-1) 0;
    transition: color var(--duration-normal) var(--ease-default);
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
  }

  .pp-evidence-trigger::before {
    content: '▸';
    display: inline-block;
    font-size: var(--text-xs);
    transition: transform var(--duration-normal) var(--ease-default);
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
    padding-top: var(--space-2);
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .pp-quote {
    background: color-mix(in srgb, var(--color-bg-surface) 76%, var(--color-bg-elevated));
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--space-2) var(--space-3);
    font-size: var(--text-sm);
    font-style: italic;
    color: var(--color-text-secondary);
    line-height: 1.55;
    margin: 0;
  }

  .pp-opp {
    display: grid;
    gap: var(--space-1);
    padding: var(--space-2) var(--space-3);
    border: 1px solid color-mix(in srgb, var(--color-accent) 18%, transparent);
    border-radius: var(--radius-md);
    background: color-mix(in srgb, var(--color-opportunity-bg) 58%, var(--color-bg-elevated));
  }

  .pp-opp p {
    margin: 0;
    color: var(--color-opportunity);
    font-size: var(--text-sm);
    line-height: 1.46;
    text-wrap: pretty;
  }

  .pp-action {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-11);
    font-weight: 700;
    color: var(--color-accent-dark);
    background: color-mix(in srgb, var(--color-bg-elevated) 88%, transparent);
    border: 1px solid color-mix(in srgb, var(--color-accent) 22%, transparent);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-full);
    cursor: pointer;
    transition:
      color var(--duration-normal) var(--ease-default),
      border-color var(--duration-normal) var(--ease-default),
      background-color var(--duration-normal) var(--ease-default),
      transform var(--duration-normal) var(--ease-default);
  }

  .pp-action:hover {
    color: var(--color-accent-dark);
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
      margin-top: var(--space-2);
    }

    .pp-pills span {
      max-width: 100%;
      white-space: normal;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .pp-card,
    .pp-card:hover,
    .pp-card--lead:hover,
    .pp-action,
    .pp-action:active,
    .pp-action-icon,
    .pp-action:hover .pp-action-icon,
    .pp-evidence-trigger::before,
    .pp-evidence[open] .pp-evidence-trigger::before {
      transform: none;
      transition: none;
    }
  }
</style>
