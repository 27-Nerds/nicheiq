<script lang="ts">
  // Pain-point detail page hero. Two-column layout mirrors IdeaHeroV2:
  // left = rank kicker + H1 + lede; right = PainPointHeroAside score panel.
  // The breadcrumb above carries category context (Home › Ideas › Niche ›
  // Sub-niche › Pain title); the rank row carries pain ranking within the
  // sub-niche.

  import type { QualitySignals } from "$lib/types/publicCatalog.js";
  import { page } from "$app/state";
  import PainPointHeroAside from "./PainPointHeroAside.svelte";
  import SaveButton from "../SaveButton.svelte";

  interface Props {
    /** CatalogPainPoint UUID — used by the SaveButton to upsert/delete the
     *  per-user save row. Optional for backward compat with consumers that
     *  haven't been threaded through yet; the Save button hides when null. */
    painPointId?: string | null;
    title: string;
    description?: string | null;
    /** Sub-niche name used in the rank-row meta line. */
    subName?: string | null;
    /** Falls back to subName for the rank-row meta if subName is null. */
    categoryName?: string | null;
    /** Comparative ranking within the sub-niche. Null on legacy rows
     *  or when computation fails. */
    rankInfo?: { rank: number; total: number } | null;
    // Aside-panel props (passed through to PainPointHeroAside).
    severity: number | null;
    willingnessToPay: number | null;
    opportunity: 'high' | 'medium' | 'low' | null;
    qualitySignals?: QualitySignals | null;
    mentionCount?: number | null;
    sourcePlatforms?: string[] | null;
  }

  let {
    painPointId = null,
    title,
    description = null,
    subName = null,
    categoryName = null,
    rankInfo = null,
    severity,
    willingnessToPay,
    opportunity,
    qualitySignals = null,
    mentionCount = null,
    sourcePlatforms = null,
  }: Props = $props();

  const rankNiche = $derived(subName ?? categoryName ?? "this niche");
</script>

<header class="pp-hero">
  <div class="left">
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
    {#if painPointId}
      <div class="hero-actions">
        <SaveButton
          itemType="painPoint"
          itemId={painPointId}
          returnTo={page.url.pathname}
        />
      </div>
    {/if}
  </div>
  <PainPointHeroAside
    {severity}
    {willingnessToPay}
    {opportunity}
    {qualitySignals}
    {mentionCount}
    {sourcePlatforms}
  />
</header>

<style>
  .pp-hero {
    display: grid;
    grid-template-columns: 1fr 320px;
    gap: 40px;
    align-items: flex-start;
    padding: 32px 0 24px;
  }
  .left {
    min-width: 0;
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
    max-width: 720px;
    text-wrap: balance;
  }
  .hero-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 22px;
  }
  .lede {
    font-size: 15px;
    color: var(--color-text-secondary, var(--color-text-primary));
    line-height: 1.6;
    max-width: 640px;
    margin: 0;
    text-wrap: pretty;
  }
  @media (max-width: 900px) {
    .pp-hero {
      grid-template-columns: 1fr;
    }
  }
</style>
