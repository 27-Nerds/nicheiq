<script lang="ts">
  interface Props {
    nicheDescription?: string;
    discussionCount: number;
    painPointCount: number;
    solutionCount: number;
    segmentCount: number;
    showFacts?: boolean;
  }

  let {
    discussionCount,
    painPointCount,
    solutionCount,
    segmentCount,
    nicheDescription,
    showFacts = true,
  }: Props = $props();
</script>

<div class="overview">
  {#if nicheDescription}
    <div class="overview-copy">
      <span class="overview-kicker">Market definition</span>
      <p class="overview-summary">{nicheDescription}</p>
    </div>
  {/if}

  {#if showFacts}
    <dl class="overview-facts" aria-label="Discovery summary">
      <div>
        <dt>Relevant discussions</dt>
        <dd>{discussionCount.toLocaleString()}</dd>
      </div>
      <div>
        <dt>Pain points</dt>
        <dd>{painPointCount}</dd>
      </div>
      <div>
        <dt>Opportunities</dt>
        <dd>{solutionCount}</dd>
      </div>
      <div>
        <dt>Segments</dt>
        <dd>{segmentCount}</dd>
      </div>
    </dl>
  {/if}
</div>

<style>
  .overview {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(13rem, 0.32fr);
    align-items: start;
    gap: var(--space-5);
  }

  .overview-copy {
    max-width: 76ch;
  }

  .overview-kicker {
    display: block;
    margin-bottom: var(--space-1-5);
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .overview-summary {
    margin: 0;
    font-size: var(--text-13);
    color: var(--color-text-secondary);
    line-height: 1.62;
    text-wrap: pretty;
  }

  .overview-facts {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-1-5);
    margin: 0;
    padding: var(--space-1-5);
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 48%, transparent);
    border-radius: var(--radius-lg);
    background:
      color-mix(in srgb, var(--color-bg-surface) 68%, transparent);
  }

  .overview-facts div {
    display: grid;
    gap: 0.08rem;
    min-width: 0;
    padding: var(--space-2);
    border-radius: var(--radius-md);
    background: color-mix(in srgb, var(--color-bg-elevated) 82%, transparent);
  }

  .overview-facts dt {
    color: var(--color-text-secondary);
    font-size: var(--text-xs);
    font-weight: 700;
    line-height: 1.2;
  }

  .overview-facts dd {
    margin: 0;
    color: var(--color-text-primary);
    font-family: var(--font-mono);
    font-size: var(--text-base);
    font-weight: 800;
    font-variant-numeric: tabular-nums;
    line-height: 1.08;
  }

  @media (max-width: 760px) {
    .overview {
      grid-template-columns: minmax(0, 1fr);
    }
  }
</style>
