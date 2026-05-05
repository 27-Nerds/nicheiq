<script lang="ts">
  // Pain-point detail page hero. The breadcrumb above carries category context
  // (Home › Ideas › Niche › Sub-niche › Pain title); the rank row carries pain
  // ranking within the sub-niche. No category-name eyebrow needed — that was
  // duplicate noise.

  interface Props {
    title: string;
    description?: string | null;
    /** Sub-niche name used in the rank-row meta line. */
    subName?: string | null;
    /** Falls back to subName for the rank-row meta if subName is null. */
    categoryName?: string | null;
    /** Comparative ranking within the sub-niche. Null on legacy rows
     *  or when computation fails. */
    rankInfo?: { rank: number; total: number } | null;
  }

  let {
    title,
    description = null,
    subName = null,
    categoryName = null,
    rankInfo = null,
  }: Props = $props();

  const rankNiche = $derived(subName ?? categoryName ?? "this niche");
</script>

<header class="pp-hero">
  {#if rankInfo}
    <div class="rank-row">
      {#if rankInfo.rank === 1}
        <span class="top-flag">Top opportunity</span>
        <span class="rank-meta">pain #1 of {rankInfo.total} in {rankNiche}</span>
      {:else}
        <span class="rank-meta">pain #{rankInfo.rank} of {rankInfo.total} in {rankNiche}</span>
      {/if}
    </div>
  {/if}
  <h1>{title}</h1>
  {#if description}
    <p class="lede">{description}</p>
  {/if}
</header>

<style>
  .pp-hero {
    padding: 32px 0 24px;
  }
  /* Rank eyebrow above the title. Mono uppercase per catalog idiom;
     accent color for the "Top opportunity" flag on rank 1. */
  .rank-row {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 10px;
    margin: 0 0 10px;
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .top-flag {
    color: var(--color-accent);
    font-weight: 700;
  }
  .rank-meta {
    color: var(--color-text-muted);
    font-weight: 600;
  }
  h1 {
    font-size: 32px;
    font-weight: 600;
    letter-spacing: -0.025em;
    line-height: 1.15;
    margin: 10px 0 14px;
    color: var(--color-text-primary);
    max-width: 820px;
    text-wrap: balance;
  }
  .lede {
    font-size: 15px;
    color: var(--color-text-secondary, var(--color-text-primary));
    line-height: 1.6;
    max-width: 720px;
    margin: 0;
    text-wrap: pretty;
  }
</style>
