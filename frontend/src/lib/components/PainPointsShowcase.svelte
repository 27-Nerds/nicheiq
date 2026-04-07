<script lang="ts">
  import CardGrid from "$lib/components/ui/CardGrid.svelte";
  import Badge from "$lib/components/ui/Badge.svelte";
  import Tooltip from "$lib/components/ui/Tooltip.svelte";
  import Button from "$lib/components/ui/Button.svelte";
  import { ArrowRight, CheckCircle } from "lucide-svelte";
  import { fade } from "svelte/transition";
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

  // Split by opportunity level
  const topOpportunities = $derived(painPoints.filter((p) => p.opportunity === "high"));
  const additionalFindings = $derived(painPoints.filter((p) => p.opportunity !== "high"));
  let additionalExpanded = $state(false);
  const ADDITIONAL_INITIAL = 4;
  const displayedAdditional = $derived(
    additionalExpanded ? additionalFindings : additionalFindings.slice(0, ADDITIONAL_INITIAL),
  );

  const highOpportunityCount = $derived(topOpportunities.length);

  const tierTooltip = $derived.by(() => {
    const tier = qualityTier?.toUpperCase();
    if (tier === "GOLD")
      return "Validated across multiple platforms with high mention density. High confidence for decision-making.";
    if (tier === "SILVER")
      return "Solid evidence base with consistent cross-platform signals. Reliable for opportunity sizing.";
    if (tier === "BRONZE")
      return "Emerging opportunity signal with limited sourcing. Useful for preliminary exploration.";
    return "Research quality assessment";
  });

  const tierVariant = $derived.by((): "success" | "accent" | "warning" | "muted" => {
    const tier = qualityTier?.toUpperCase();
    if (tier === "GOLD") return "success";
    if (tier === "SILVER") return "accent";
    if (tier === "BRONZE") return "warning";
    return "muted";
  });

  const anchorText = $derived.by(() => {
    const mentions = totalMentions && totalMentions > 0
      ? ` across ${totalMentions.toLocaleString()} discussions`
      : "";

    if (highOpportunityCount > 0) {
      return `Strong market signal: ${highOpportunityCount} high-opportunity pain point${highOpportunityCount > 1 ? "s" : ""} with verified willingness-to-pay${mentions}`;
    }
    if (painPoints.length > 0 && mentions) {
      return `${painPoints.length} validated pain points identified${mentions}`;
    }
    return null;
  });

  function severityColor(severity: number): string {
    if (severity > 0.75) return "var(--color-error)";
    if (severity > 0.55) return "var(--color-warning)";
    return "var(--color-text-muted)";
  }

  function wtpDisplay(wtp: number): string {
    if (wtp >= 0.66) return "$$$";
    if (wtp >= 0.33) return "$$";
    return "$";
  }

  function opportunityVariant(opp: string): "success" | "accent" | "muted" {
    if (opp === "high") return "success";
    if (opp === "medium") return "accent";
    return "muted";
  }

  // Global rank counter across both sections
  function globalRank(point: PainPointSummary): number {
    return painPoints.indexOf(point) + 1;
  }
</script>

<div class="showcase">
  <!-- Headline-first header -->
  <div class="showcase-header">
    <div class="showcase-header-row">
      <h2 class="showcase-headline">
        {#if highOpportunityCount > 0}
          {highOpportunityCount} High-Opportunity Pain Point{highOpportunityCount > 1 ? "s" : ""} Found
        {:else}
          {painPoints.length} Pain Point{painPoints.length > 1 ? "s" : ""} Identified
        {/if}
      </h2>
      {#if qualityTier}
        <Tooltip content={tierTooltip}>
          {#snippet children()}
            <Badge variant={tierVariant} size="sm">{qualityTier}</Badge>
          {/snippet}
        </Tooltip>
      {/if}
    </div>
    <p class="showcase-scope">
      {painPoints.length} signals identified{totalMentions ? ` across ${totalMentions.toLocaleString()} discussions` : ""}
    </p>
  </div>

  {#if anchorText}
    <div class="anchor-strip">
      <p class="anchor-text">{anchorText}</p>
    </div>
  {/if}

  <hr class="divider" />

  <!-- Top Opportunities (HIGH only) -->
  {#if topOpportunities.length > 0}
    <div class="section-group">
      <span class="section-label">Top Opportunities</span>
      <div class="top-grid">
        {#each topOpportunities as point, i (point.title)}
          <article
            class="pp-card animate-fade-slide-in"
            style="animation-delay: {i * 60}ms"
            aria-label="{point.title} — severity {(point.severity * 10).toFixed(1)}/10"
          >
            <div class="pp-card-header">
              <span class="pp-rank">#{globalRank(point)}</span>
              <h3 class="pp-title">{point.title}</h3>
              <Badge variant={opportunityVariant(point.opportunity)} size="sm">
                {point.opportunity}
              </Badge>
            </div>
            {#if point.short_summary}
              <p class="pp-desc">{point.short_summary}</p>
            {/if}
            <div class="pp-metrics">
              <span class="pp-wtp">
                {wtpDisplay(point.wtp)}<span class="pp-wtp-label">WTP</span>
              </span>
              <span class="pp-mentions">
                {point.mentions.toLocaleString()} discussions
              </span>
              <span class="pp-severity" style="color: {severityColor(point.severity)}">
                {(point.severity * 10).toFixed(1)}/10
              </span>
            </div>
            {#if discoveryQuotes?.[point.title]?.length}
              {@const q = discoveryQuotes[point.title][0]}
              <div class="pp-quote" in:fade={{ duration: 200 }}>
                <span class="pp-quote-upvote">&#9650; {q.upvotes.toLocaleString()}</span>
                <span class="pp-quote-text">&ldquo;{q.text.length > 180 ? q.text.slice(0, 177) + '...' : q.text}&rdquo;</span>
                <span class="pp-quote-attr">
                  {#if q.subreddit}r/{q.subreddit}{/if}
                  {#if q.source_url}
                    &middot; <a href={q.source_url} target="_blank" rel="noopener noreferrer" class="pp-quote-link">View source &rarr;</a>
                  {/if}
                </span>
              </div>
            {/if}
          </article>
        {/each}
      </div>
    </div>
  {/if}

  <!-- Additional Findings (MEDIUM/LOW) -->
  {#if additionalFindings.length > 0}
    <div class="section-group">
      {#if topOpportunities.length > 0}
        <span class="section-label section-label--secondary">Additional Findings</span>
      {/if}
      <CardGrid minWidth={320} gap="lg">
        {#each displayedAdditional as point, i (point.title)}
          <article
            class="pp-card animate-fade-slide-in"
            style="animation-delay: {(topOpportunities.length + i) * 60}ms"
            aria-label="{point.title} — severity {(point.severity * 10).toFixed(1)}/10"
          >
            <div class="pp-card-header">
              <span class="pp-rank">#{globalRank(point)}</span>
              <h3 class="pp-title">{point.title}</h3>
              <Badge variant={opportunityVariant(point.opportunity)} size="sm">
                {point.opportunity}
              </Badge>
            </div>
            {#if point.short_summary}
              <p class="pp-desc">{point.short_summary}</p>
            {/if}
            <div class="pp-metrics">
              <span class="pp-wtp">
                {wtpDisplay(point.wtp)}<span class="pp-wtp-label">WTP</span>
              </span>
              <span class="pp-mentions">
                {point.mentions.toLocaleString()} discussions
              </span>
              <span class="pp-severity" style="color: {severityColor(point.severity)}">
                {(point.severity * 10).toFixed(1)}/10
              </span>
            </div>
            {#if discoveryQuotes?.[point.title]?.length}
              {@const q = discoveryQuotes[point.title][0]}
              <div class="pp-quote" in:fade={{ duration: 200 }}>
                <span class="pp-quote-upvote">&#9650; {q.upvotes.toLocaleString()}</span>
                <span class="pp-quote-text">&ldquo;{q.text.length > 180 ? q.text.slice(0, 177) + '...' : q.text}&rdquo;</span>
                <span class="pp-quote-attr">
                  {#if q.subreddit}r/{q.subreddit}{/if}
                  {#if q.source_url}
                    &middot; <a href={q.source_url} target="_blank" rel="noopener noreferrer" class="pp-quote-link">View source &rarr;</a>
                  {/if}
                </span>
              </div>
            {/if}
          </article>
        {/each}
      </CardGrid>

      {#if additionalFindings.length > ADDITIONAL_INITIAL}
        <div class="expand-row">
          <button
            type="button"
            class="expand-btn"
            aria-expanded={additionalExpanded}
            onclick={() => { additionalExpanded = !additionalExpanded; }}
          >
            {additionalExpanded
              ? "Show fewer"
              : `Show all ${additionalFindings.length} additional findings`}
          </button>
        </div>
      {/if}
    </div>
  {/if}

  <!-- Reveal CTA / After-Reveal -->
  <hr class="divider" />

  {#if !ideasRevealed}
    <div class="cta-section">
      <span class="cta-label">Solutions Ready</span>
      <p class="cta-desc">
        Your research identified
        <strong class="cta-count">{solutionCount}</strong> solution opportunities ranked by market fit
      </p>

      <div class="cta-checks">
        <span class="cta-check">
          <CheckCircle class="cta-check-icon" />
          Each addresses your highest-severity pain points
        </span>
        <span class="cta-check">
          <CheckCircle class="cta-check-icon" />
          Ranked by market fit and technical feasibility
        </span>
      </div>

      {#if solutionNames.length > 0}
        <p class="cta-teaser-hint">
          Including "{solutionNames[0]}"{solutionNames.length > 1 ? ` and ${solutionNames.length - 1} more` : ''}
        </p>
      {/if}

      <div class="cta-button-wrap">
        <Button
          onclick={onRevealIdeas}
          icon={ArrowRight}
          iconPosition="end"
          label="See your {solutionCount} validated solution ideas"
          class="btn-primary cta-btn"
        />
      </div>

      <p class="cta-reassurance">
        Already in your research · No additional credits
      </p>
    </div>
  {:else}
    <div class="after-reveal">
      <CheckCircle class="after-reveal-icon" />
      <span class="after-reveal-text">
        Solutions ready for review · {solutionCount} ideas tailored to your market
      </span>
    </div>
  {/if}
</div>

<style>
  .showcase {
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: var(--space-6);
  }

  /* ===== Headline-first header ===== */
  .showcase-header {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
    margin-bottom: var(--space-3);
  }

  .showcase-header-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
  }

  .showcase-headline {
    font-family: var(--font-display);
    font-size: var(--text-xl);
    font-weight: 700;
    color: var(--color-text-primary);
    margin: 0;
    line-height: 1.3;
  }

  .showcase-scope {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 500;
    color: var(--color-text-muted);
    margin: 0;
    letter-spacing: 0.02em;
    font-variant-numeric: tabular-nums;
  }

  /* ===== Anchor callout ===== */
  .anchor-strip {
    margin-top: var(--space-3);
    padding: var(--space-2) var(--space-3);
    background: var(--color-accent-glow);
    border-left: 2px solid var(--color-border-accent);
    border-radius: var(--radius-md);
  }

  .anchor-text {
    font-size: var(--text-sm);
    color: var(--color-text-secondary);
    margin: 0;
  }

  .showcase > .divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--color-border-emphasis), transparent);
    border: none;
    margin: var(--space-5) 0;
  }

  /* ===== Section groups ===== */
  .section-group {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .section-group + .section-group {
    margin-top: var(--space-5);
  }

  .section-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--color-text-muted);
  }

  .section-label--secondary {
    color: var(--color-text-muted);
    opacity: 0.7;
  }

  /* Top Opportunities: single-column layout */
  .top-grid {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  /* ===== Pain Point Cards ===== */
  .pp-card {
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: var(--space-5);
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .pp-card-header {
    display: flex;
    align-items: flex-start;
    gap: var(--space-2);
  }

  .pp-rank {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--color-text-muted);
    flex-shrink: 0;
    padding-top: 0.125rem;
  }

  .pp-title {
    font-family: var(--font-display);
    font-size: var(--text-base);
    font-weight: 600;
    color: var(--color-text-primary);
    line-height: 1.35;
    flex: 1;
    min-width: 0;
    margin: 0;
  }

  .pp-desc {
    font-size: var(--text-sm);
    color: var(--color-text-secondary);
    line-height: 1.5;
    margin: 0;
  }

  .pp-metrics {
    display: flex;
    align-items: center;
    gap: var(--space-4);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    font-variant-numeric: tabular-nums;
    margin-top: var(--space-1);
  }

  .pp-wtp {
    font-weight: 700;
    color: var(--color-success);
    letter-spacing: -0.02em;
  }

  .pp-wtp-label {
    font-weight: 500;
    font-size: 0.5625rem;
    color: var(--color-text-muted);
    margin-left: 0.25rem;
    letter-spacing: 0.04em;
  }

  .pp-mentions {
    color: var(--color-text-secondary);
  }

  .pp-severity {
    font-weight: 600;
    margin-left: auto;
  }

  /* ===== Inline Quotes ===== */
  .pp-quote {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0.25rem;
    margin-top: var(--space-2);
    padding-top: var(--space-2);
    border-top: 1px solid var(--color-border);
  }

  .pp-quote-upvote {
    font-family: var(--font-mono);
    font-weight: 600;
    font-size: var(--text-sm);
    color: var(--color-accent);
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
  }

  .pp-quote-text {
    font-size: var(--text-sm);
    font-style: italic;
    color: var(--color-text-secondary);
    line-height: 1.5;
  }

  .pp-quote-attr {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--color-text-muted);
    width: 100%;
    margin-top: var(--space-1);
  }

  .pp-quote-link {
    color: var(--color-text-muted);
    text-decoration: none;
    transition: color var(--duration-fast) ease;
  }

  .pp-quote-link:hover {
    color: var(--color-accent);
  }

  .pp-quote-link:active {
    transform: scale(0.98);
  }

  /* ===== Expand ===== */
  .expand-row {
    display: flex;
    justify-content: center;
    margin-top: var(--space-2);
  }

  .expand-btn {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 500;
    color: var(--color-text-muted);
    background: none;
    border: none;
    cursor: pointer;
    padding: var(--space-2) var(--space-4);
    border-radius: var(--radius-md);
    transition: color var(--duration-fast) ease, background var(--duration-fast) ease;
  }

  .expand-btn:hover {
    color: var(--color-text-secondary);
    background: var(--color-bg-surface);
  }

  .expand-btn:active {
    transform: scale(0.98);
  }

  /* ===== CTA Section ===== */
  .cta-section {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: var(--space-3);
    padding: var(--space-4) 0;
  }

  .cta-desc {
    font-size: var(--text-sm);
    color: var(--color-text-secondary);
    margin: 0;
    max-width: 360px;
  }

  .cta-count {
    font-family: var(--font-mono);
    font-weight: 700;
    color: var(--color-accent);
    font-variant-numeric: tabular-nums;
  }

  .cta-checks {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    align-items: center;
  }

  .cta-check {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    font-size: var(--text-xs);
    color: var(--color-text-muted);
  }

  :global(.cta-check-icon) {
    width: 0.75rem;
    height: 0.75rem;
    color: var(--color-success);
    flex-shrink: 0;
  }

  .cta-teaser-hint {
    font-size: var(--text-xs);
    font-style: italic;
    color: var(--color-text-muted);
    margin: 0;
  }

  .cta-button-wrap {
    margin-top: var(--space-2);
  }

  .cta-button-wrap :global(.cta-btn) {
    padding: 0.75rem 1.5rem;
    font-size: var(--text-base);
  }

  .cta-button-wrap :global(.cta-btn:active) {
    transform: scale(0.98);
  }

  .cta-reassurance {
    font-size: var(--text-xs);
    color: var(--color-text-muted);
    margin: 0;
  }

  /* ===== After Reveal ===== */
  .after-reveal {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    padding: var(--space-3) 0;
  }

  :global(.after-reveal-icon) {
    width: 1rem;
    height: 1rem;
    color: var(--color-success);
    flex-shrink: 0;
  }

  .after-reveal-text {
    font-size: var(--text-sm);
    color: var(--color-success);
  }

  /* ===== Responsive ===== */
  @media (max-width: 768px) {
    .showcase {
      padding: var(--space-4);
    }

    .showcase-headline {
      font-size: var(--text-lg);
    }

    .pp-metrics {
      flex-wrap: wrap;
      gap: var(--space-2) var(--space-4);
    }

    .pp-severity {
      margin-left: 0;
    }
  }
</style>
