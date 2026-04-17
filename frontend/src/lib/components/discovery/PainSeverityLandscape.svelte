<script lang="ts">
  import Badge from "$lib/components/ui/Badge.svelte";
  import Button from "$lib/components/ui/Button.svelte";
  import { ArrowRight, ArrowUpRight, CheckCircle } from "lucide-svelte";
  import type { PainPointSummary } from "$lib/types/stageArtifacts";
  import type { DiscoveryQuote } from "$lib/types/discovery";

  interface Props {
    painPoints: PainPointSummary[];
    totalMentions?: number;
    qualityTier?: string;
    confidence?: number;
    solutionCount: number;
    solutionNames: string[];
    ideasRevealed: boolean;
    onRevealIdeas: () => void;
    discoveryQuotes?: Record<string, DiscoveryQuote[]>;
  }

  let {
    painPoints,
    totalMentions,
    qualityTier,
    confidence,
    solutionCount,
    solutionNames,
    ideasRevealed,
    onRevealIdeas,
    discoveryQuotes,
  }: Props = $props();

  // Sort by severity descending
  const sortedPoints = $derived(
    [...painPoints].sort((a, b) => b.severity - a.severity)
  );

  // Pure functions for per-item rendering
  function severityClass(s: number): string {
    if (s > 0.65) return 'pain-card pain-card-severity-high';
    if (s > 0.45) return 'pain-card pain-card-severity-medium';
    return 'pain-card';
  }

  function wtpDisplay(wtp: number): string {
    if (wtp >= 0.66) return '$$$';
    if (wtp >= 0.33) return '$$';
    return '$';
  }

  function quotesForPoint(title: string, max: number): DiscoveryQuote[] {
    return (discoveryQuotes?.[title] ?? []).slice(0, max);
  }

  function totalQuotesForPoint(title: string): number {
    return discoveryQuotes?.[title]?.length ?? 0;
  }
</script>

<section class="landscape">
  <div class="section-header-meta">
    <div class="section-header-bar"></div>
    <span class="landscape-label">Validated Pain Points</span>
    <span class="landscape-stat">
      {painPoints.length} signals{#if totalMentions} &middot; {totalMentions.toLocaleString()} discussions{/if}
    </span>
  </div>

  <div class="landscape-cards">
    {#each sortedPoints as point, i (point.title)}
      {@const isFirst = i === 0}
      {@const maxQuotes = isFirst ? 2 : 1}
      {@const quotes = quotesForPoint(point.title, maxQuotes)}
      {@const totalQ = totalQuotesForPoint(point.title)}

      <article
        class={severityClass(point.severity)}
        style="--severity-fill: {(point.severity * 100).toFixed(0)}%"
      >
        <div class="pc-header">
          <span class="pc-rank">#{i + 1}</span>
          <h3 class="pc-title">{point.title}</h3>
        </div>

        {#if point.short_summary}
          <p class="pc-desc">{point.short_summary}</p>
        {/if}

        <div class="pc-metrics">
          <span class="pc-severity">{(point.severity * 10).toFixed(1)}/10</span>
          <span class="pc-wtp">{wtpDisplay(point.wtp)}<span class="pc-wtp-label">WTP</span></span>
          <span class="pc-mentions">{point.mentions.toLocaleString()} discussions</span>
        </div>

        {#if quotes.length > 0}
          <div class="pc-quotes">
            {#each quotes as q}
              <div class="pc-quote-row">
                <span class="pc-quote-upvote">&#9650; {q.upvotes.toLocaleString()}</span>
                <span class="pc-quote-text">&ldquo;{q.text.length > 200 ? q.text.slice(0, 197) + '...' : q.text}&rdquo;</span>
              </div>
              <div class="pc-quote-attr">
                {#if q.subreddit}{q.subreddit}{/if}
                {#if q.source_url}
                  <span class="pc-quote-sep">&middot;</span>
                  <a href={q.source_url} target="_blank" rel="noopener noreferrer" class="pc-quote-link">
                    View source <ArrowUpRight size={10} />
                  </a>
                {/if}
              </div>
            {/each}
            {#if totalQ > maxQuotes}
              <span class="pc-quote-more">Showing {maxQuotes} of {totalQ} verified quotes</span>
            {/if}
          </div>
        {/if}
      </article>
    {/each}
  </div>

  <!-- CTA Section -->
  <div class="landscape-cta">
    {#if !ideasRevealed}
      <p class="cta-desc">
        <strong>{solutionCount}</strong> solution ideas matched to these pain points
      </p>
      <Button
        onclick={onRevealIdeas}
        icon={ArrowRight}
        iconPosition="end"
        label="See your {solutionCount} solutions built from this research"
        class="btn-primary"
      />
      <p class="cta-reassurance">Already in your research &middot; No additional credits</p>
    {:else}
      <div class="cta-done">
        <CheckCircle class="cta-done-icon" />
        <span>Solutions ready &middot; {solutionCount} ideas tailored to your market</span>
      </div>
    {/if}
  </div>
</section>

<style>
  .landscape {
    margin: var(--space-4) 0;
  }

  .landscape-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--color-text-muted);
  }

  .landscape-stat {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--color-text-muted);
    margin-left: auto;
    font-variant-numeric: tabular-nums;
  }

  .landscape-cards {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    margin-top: var(--space-3);
  }

  /* Severity-proportional left bar override */
  .landscape :global(.pain-card::before) {
    height: var(--severity-fill, 100%);
    bottom: auto;
  }

  /* Pain card inner layout */
  .pc-header {
    display: flex;
    align-items: flex-start;
    gap: var(--space-2);
    margin-bottom: var(--space-1);
  }

  .pc-rank {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--color-text-muted);
    flex-shrink: 0;
    padding-top: 0.125rem;
  }

  .pc-title {
    font-family: var(--font-display);
    font-size: var(--text-base);
    font-weight: 600;
    color: var(--color-text-primary);
    line-height: 1.35;
    margin: 0;
  }

  .pc-desc {
    font-size: var(--text-sm);
    color: var(--color-text-secondary);
    line-height: 1.5;
    margin: 0 0 var(--space-1);
  }

  .pc-metrics {
    display: flex;
    align-items: center;
    gap: var(--space-4);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    font-variant-numeric: tabular-nums;
  }

  .pc-severity {
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .pc-wtp {
    font-weight: 700;
    color: var(--color-success);
    letter-spacing: -0.02em;
  }

  .pc-wtp-label {
    font-weight: 500;
    font-size: 0.5625rem;
    color: var(--color-text-muted);
    margin-left: 0.25rem;
    letter-spacing: 0.04em;
  }

  .pc-mentions {
    color: var(--color-text-secondary);
  }

  /* Quotes section */
  .pc-quotes {
    margin-top: var(--space-3);
    padding-top: var(--space-3);
    border-top: 1px solid rgba(0, 0, 0, 0.05);
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .pc-quote-row {
    display: flex;
    align-items: baseline;
    gap: 0.375rem;
  }

  .pc-quote-upvote {
    font-family: var(--font-mono);
    font-weight: 600;
    font-size: var(--text-sm);
    color: var(--color-accent);
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
  }

  .pc-quote-text {
    font-size: var(--text-sm);
    font-style: italic;
    color: var(--color-text-secondary);
    line-height: 1.5;
  }

  .pc-quote-attr {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--color-text-muted);
    margin-top: var(--space-1);
    padding-left: 2.5rem;
  }

  .pc-quote-sep {
    opacity: 0.4;
  }

  .pc-quote-link {
    color: var(--color-text-muted);
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    gap: 0.125rem;
    transition: color var(--duration-fast) ease;
  }

  .pc-quote-link:hover {
    color: var(--color-accent);
  }

  .pc-quote-link:active {
    transform: scale(0.98);
  }

  .pc-quote-more {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--color-text-muted);
    padding-left: 2.5rem;
  }

  /* CTA */
  .landscape-cta {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-6) 0 var(--space-4);
    text-align: center;
  }

  .cta-desc {
    font-size: var(--text-sm);
    color: var(--color-text-secondary);
    margin: 0;
  }

  .cta-reassurance {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--color-text-muted);
    margin: 0;
  }

  .cta-done {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-sm);
    color: var(--color-success);
  }

  .cta-done :global(.cta-done-icon) {
    width: 1rem;
    height: 1rem;
  }
</style>
