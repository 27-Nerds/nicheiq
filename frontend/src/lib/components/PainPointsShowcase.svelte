<script lang="ts">
  import CardGrid from "$lib/components/ui/CardGrid.svelte";
  import Badge from "$lib/components/ui/Badge.svelte";
  import Tooltip from "$lib/components/ui/Tooltip.svelte";
  import Button from "$lib/components/ui/Button.svelte";
  import { ArrowRight, CheckCircle } from "lucide-svelte";
  import type { PainPointSummary } from "$lib/types/stageArtifacts";

  interface Props {
    painPoints: PainPointSummary[];
    totalMentions?: number;
    qualityTier?: string;
    confidence?: number;
    solutionCount: number;
    solutionNames: string[];
    ideasRevealed: boolean;
    onRevealIdeas: () => void;
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
  }: Props = $props();

  let expanded = $state(false);

  const INITIAL_SHOW = 7;

  const highOpportunityCount = $derived(
    painPoints.filter((p) => p.opportunity === "high").length,
  );

  const mediumOpportunityCount = $derived(
    painPoints.filter((p) => p.opportunity === "medium").length,
  );

  const displayedPoints = $derived(
    expanded ? painPoints : painPoints.slice(0, INITIAL_SHOW),
  );

  const anchorText = $derived.by(() => {
    const mentions = totalMentions && totalMentions > 0
      ? ` across ${totalMentions.toLocaleString()} discussions`
      : "";

    if (highOpportunityCount > 0) {
      return `Strong market signal: ${highOpportunityCount} high-opportunity pain point${highOpportunityCount > 1 ? "s" : ""} with verified willingness-to-pay${mentions}`;
    }
    if (mediumOpportunityCount > 0) {
      return `${painPoints.length} validated pain points identified${mentions}`;
    }
    if (painPoints.length > 0) {
      return `${painPoints.length} pain points identified from community discussions${mentions}`;
    }
    return null;
  });

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


</script>

<!-- Research Findings -->
<div class="showcase">
  <div class="showcase-header">
    <div class="showcase-header-row">
      <span class="showcase-label">Research Findings</span>
      {#if qualityTier}
        <Tooltip content={tierTooltip}>
          {#snippet children()}
            <Badge variant={tierVariant} size="sm">{qualityTier}</Badge>
          {/snippet}
        </Tooltip>
      {/if}
    </div>
    <span class="showcase-subtitle"
      >Verified pain points from real community discussions</span
    >
  </div>

  {#if anchorText}
    <div class="anchor-strip">
      <p class="anchor-text">{anchorText}</p>
    </div>
  {/if}

  <hr class="divider" />

  <!-- Pain Point Card Grid -->
  <CardGrid minWidth={320} gap="lg">
    {#each displayedPoints as point, i (point.title)}
      <article
        class="pp-card animate-fade-slide-in"
        style="animation-delay: {Math.min(i, INITIAL_SHOW - 1) * 60}ms"
        aria-label="{point.title} — severity {(point.severity * 10).toFixed(1)}/10"
      >
        <!-- Rank + Title + Opportunity -->
        <div class="pp-card-header">
          <span class="pp-rank">#{i + 1}</span>
          <h3 class="pp-title">{point.title}</h3>
          <Badge
            variant={opportunityVariant(point.opportunity)}
            size="sm"
          >
            {point.opportunity}
          </Badge>
        </div>

        <!-- Short summary -->
        {#if point.short_summary}
          <p class="pp-desc">{point.short_summary}</p>
        {/if}

        <!-- Metrics: WTP + Mentions + Severity -->
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

      </article>
    {/each}
  </CardGrid>

  <!-- Miller's Chunking: Expand -->
  {#if painPoints.length > INITIAL_SHOW}
    <div class="expand-row">
      <button
        type="button"
        class="expand-btn"
        aria-expanded={expanded}
        onclick={() => { expanded = !expanded; }}
      >
        {expanded
          ? `Show fewer`
          : `Show all ${painPoints.length} findings`}
      </button>
    </div>
  {/if}

  <!-- Reveal CTA / After-Reveal -->
  <hr class="divider" />

  {#if !ideasRevealed}
    <div class="cta-section">
      <span class="cta-label">Ready for Solutions</span>
      <p class="cta-desc">
        Based on your pain points, we generated
        <strong class="cta-count">{solutionCount}</strong> tailored solution ideas
      </p>

      {#if solutionNames.length > 0}
        <ul class="cta-teasers">
          {#each solutionNames as name}
            <li>{name}</li>
          {/each}
        </ul>
      {/if}

      <div class="cta-button-wrap">
        <Button
          onclick={onRevealIdeas}
          icon={ArrowRight}
          iconPosition="end"
          label="Continue to Solutions"
          class="btn-primary btn-shimmer cta-btn"
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

  .showcase-header {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    margin-bottom: var(--space-3);
  }

  .showcase-header-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
  }

  .showcase-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--color-text-muted);
  }

  .showcase-subtitle {
    font-size: var(--text-sm);
    color: var(--color-text-secondary);
  }

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
    background: linear-gradient(
      90deg,
      transparent,
      var(--color-border-emphasis),
      transparent
    );
    border: none;
    margin: var(--space-5) 0;
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

  /* ===== Expand ===== */
  .expand-row {
    display: flex;
    justify-content: center;
    margin-top: var(--space-3);
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
    transition: color var(--duration-fast) ease,
      background var(--duration-fast) ease;
  }

  .expand-btn:hover {
    color: var(--color-text-secondary);
    background: var(--color-bg-surface);
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

  .cta-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--color-text-muted);
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

  .cta-teasers {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .cta-teasers li {
    font-size: var(--text-sm);
    color: var(--color-text-secondary);
  }

  .cta-teasers li::before {
    content: "·  ";
    color: var(--color-text-muted);
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

    .pp-metrics {
      flex-wrap: wrap;
      gap: var(--space-2) var(--space-4);
    }

    .pp-severity {
      margin-left: 0;
    }
  }
</style>
