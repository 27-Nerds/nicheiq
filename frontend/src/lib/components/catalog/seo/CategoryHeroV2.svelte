<script lang="ts">
  import IconBadge from "./IconBadge.svelte";
  import StatStrip, { type Stat } from "./StatStrip.svelte";
  import QualityTierBadge from "./QualityTierBadge.svelte";
  import { categoryIcon } from "$lib/utils/categoryIcons";
  import type { NicheContext, QualitySignals } from "$lib/types/publicCatalog.js";

  // Mockup `.page-hero` for category + sub-category pages.
  // - icon-badge + optional growth pill (hidden until pipeline ships growth%)
  // - H1 + lede
  // - 4-tile stat strip

  interface Props {
    name: string;
    slug: string;
    description?: string | null;
    /** "Sub-niche of X" pill content. Pass null for top-level categories. */
    parentChip?: { name: string; slug: string } | null;
    /** Reserved — when backend ships growth%, render an accent pill. */
    growthPercent?: number | null;
    /** 4 tiles for the stat strip. */
    stats: Stat[];
    /** Phase 5.5 — niche-context blob; nicheContext.description supersedes
     *  `description` in the lede when present. industryBoundaries renders as a
     *  single inline pill (Pydantic field is `str`, NOT an array). */
    nicheContext?: NicheContext | null;
    /** Phase 5.5 — quality tier pill in the meta row. */
    qualitySignals?: QualitySignals | null;
  }

  let {
    name,
    slug,
    description = null,
    parentChip = null,
    growthPercent = null,
    stats,
    nicheContext = null,
    qualitySignals = null,
  }: Props = $props();

  const Icon = $derived(categoryIcon(slug));
  // Prefer the LLM-generated niche_description; fall back to the catalog
  // category's short description string for legacy rows.
  const lede = $derived(nicheContext?.description ?? description);
  const industryBoundaries = $derived(nicheContext?.industryBoundaries ?? null);
  const marketSegments = $derived(nicheContext?.marketSegments ?? null);
</script>

<header class="page-hero">
  <div class="meta-row">
    <IconBadge size={32}>
      <Icon size={16} />
    </IconBadge>
    {#if parentChip}
      <a class="badge" href={`/ideas/${parentChip.slug}`}>
        <span class="badge-key">Sub-niche of</span>
        {parentChip.name}
      </a>
    {/if}
    {#if growthPercent != null}
      <span class="badge accent">↗ {growthPercent}% this month</span>
    {/if}
    {#if qualitySignals}
      <QualityTierBadge signals={qualitySignals} />
    {/if}
  </div>
  <h1>{name}</h1>
  {#if lede}
    <p class="lede">{lede}</p>
  {/if}
  {#if industryBoundaries || (marketSegments && marketSegments.length > 0)}
    <div class="boundary-row">
      {#if industryBoundaries}
        <span class="boundary-pill">
          <span class="boundary-key">Industry</span>
          {industryBoundaries}
        </span>
      {/if}
      {#if marketSegments && marketSegments.length > 0}
        {#each marketSegments as seg}
          <span class="boundary-chip">{seg}</span>
        {/each}
      {/if}
    </div>
  {/if}
  <div class="strip-wrap">
    <StatStrip {stats} />
  </div>
</header>

<style>
  .page-hero {
    padding: 32px 0;
  }
  .meta-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 14px;
    flex-wrap: wrap;
  }
  .badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 9px;
    border-radius: 5px;
    font-size: 11px;
    font-weight: 500;
    border: 1px solid var(--color-border);
    color: var(--color-text-secondary, var(--color-text-primary));
    background: var(--color-surface, #fff);
    text-decoration: none;
    transition: border-color 0.12s;
  }
  .badge:hover {
    border-color: var(--color-border-emphasis);
  }
  .badge-key {
    color: var(--color-text-muted);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 600;
  }
  .badge.accent {
    color: var(--color-accent);
    border-color: var(--color-border-accent);
    background: var(--color-accent-glow, rgba(240, 96, 48, 0.04));
  }
  h1 {
    margin: 0 0 14px;
    font-size: 36px;
    font-weight: 600;
    letter-spacing: -0.025em;
    line-height: 1.1;
    color: var(--color-text-primary);
  }
  .lede {
    font-size: 15px;
    color: var(--color-text-secondary, var(--color-text-primary));
    line-height: 1.6;
    max-width: 620px;
    margin: 0 0 16px;
  }
  /* Boundary row — industry pill + market-segment chips. Sits below the lede
     so the prose lead has its own visual weight. */
  .boundary-row {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin: 0 0 24px;
  }
  .boundary-pill,
  .boundary-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 11px;
    border: 1px solid var(--color-border);
    color: var(--color-text-secondary, var(--color-text-primary));
    background: var(--color-surface, #fff);
  }
  .boundary-key {
    font-family: var(--font-mono);
    font-size: 9px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    font-weight: 600;
  }
  .strip-wrap {
    margin-top: 28px;
  }
</style>
