<script lang="ts">
  interface Props {
    nicheName: string;
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
    gap: 1.18rem;
  }

  .overview-copy {
    max-width: 76ch;
  }

  .overview-kicker {
    display: block;
    margin-bottom: 0.36rem;
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: 0.58rem;
    font-weight: 780;
    letter-spacing: 0.055em;
    text-transform: uppercase;
  }

  .overview-summary {
    margin: 0;
    font-size: 0.84rem;
    color: var(--color-text-secondary);
    line-height: 1.62;
    text-wrap: pretty;
  }

  .overview-facts {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.34rem;
    margin: 0;
    padding: 0.36rem;
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 48%, transparent);
    border-radius: 0.72rem;
    background:
      color-mix(in srgb, var(--color-bg-surface) 68%, transparent);
  }

  .overview-facts div {
    display: grid;
    gap: 0.08rem;
    min-width: 0;
    padding: 0.48rem 0.52rem;
    border-radius: 0.52rem;
    background: color-mix(in srgb, var(--color-bg-elevated) 82%, transparent);
  }

  .overview-facts dt {
    color: var(--color-text-muted);
    font-size: 0.58rem;
    font-weight: 720;
    line-height: 1.2;
  }

  .overview-facts dd {
    margin: 0;
    color: var(--color-text-primary);
    font-family: var(--font-mono);
    font-size: 0.9rem;
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
