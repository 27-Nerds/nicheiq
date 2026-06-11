<script lang="ts">
  // Pain-point detail page hero. Two-column layout mirrors IdeaHeroV2:
  // left = rank kicker + H1 + lede; right = PainPointHeroAside score panel.
  // The breadcrumb above carries category context (Home › Ideas › Niche ›
  // Sub-niche › Pain title); the rank row carries pain ranking within the
  // sub-niche.

  import type { QualitySignals, Theme } from "$lib/types/publicCatalog.js";
  import { page } from "$app/state";
  import PainPointHeroAside from "./PainPointHeroAside.svelte";
  import { PAIN_ICON as PainIcon } from "$lib/config/entity-icons";
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
    /** Parent theme this pain belongs to (matched at the route via pp.themeId
     *  → data.painPoint.themes). When set, renders a sibling theme-row
     *  beneath the rank-row as a lightweight discoverability hint. */
    parentTheme?: Theme | null;
    /** Pre-built href to the theme's anchor on the niche/sub-niche page
     *  (e.g. /ideas/foo/bar#theme-{id}). When non-null, theme-row renders an
     *  anchor; when null, plain text. Avoids href={x ?? '#'} fake-affordance. */
    themeAnchorHref?: string | null;
    // Aside-panel props (passed through to PainPointHeroAside).
    severity: number | null;
    willingnessToPay: number | null;
    opportunity: 'high' | 'medium' | 'low' | null;
    qualitySignals?: QualitySignals | null;
    mentionCount?: number | null;
    sourcePlatforms?: string[] | null;
    /** ISO date string used in the visible byline. Should match the schema's
     *  `dateModified` so visible-vs-schema match holds for the Article block. */
    updatedAt?: string | null;
    /** Author label rendered in the byline. Should match the schema's
     *  `Article.author.name`. */
    authorName?: string;
  }

  let {
    painPointId = null,
    title,
    description = null,
    subName = null,
    categoryName = null,
    rankInfo = null,
    parentTheme = null,
    themeAnchorHref = null,
    severity,
    willingnessToPay,
    opportunity,
    qualitySignals = null,
    mentionCount = null,
    sourcePlatforms = null,
    updatedAt = null,
    authorName = "NicheIQ Research Team",
  }: Props = $props();

  const rankNiche = $derived(subName ?? categoryName ?? "this niche");

  const updatedDisplay = $derived.by(() => {
    if (!updatedAt) return null;
    try {
      return new Intl.DateTimeFormat("en-US", {
        year: "numeric",
        month: "long",
        day: "numeric",
      }).format(new Date(updatedAt));
    } catch {
      return null;
    }
  });
</script>

<header class="pp-hero">
  <div class="left">
    <p class="entity-eyebrow">
      <PainIcon size={14} aria-hidden="true" />
      <span>Pain point</span>
    </p>
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
    {#if parentTheme}
      <div class="theme-row">
        {#if themeAnchorHref}
          <a class="theme-link" href={themeAnchorHref}>↗ Theme · {parentTheme.title}</a>
        {:else}
          <span class="theme-link static">Theme · {parentTheme.title}</span>
        {/if}
      </div>
    {/if}
    <h1>{title}</h1>
    {#if updatedDisplay}
      <!-- Byline anchors the Article schema's author + dateModified visibly
           on the page — required by Google's Article guidelines. -->
      <p class="byline">
        <span class="byline-author">By {authorName}</span>
        <span class="byline-sep" aria-hidden="true">·</span>
        <span class="byline-updated">
          Updated <time datetime={updatedAt!}>{updatedDisplay}</time>
        </span>
      </p>
    {/if}
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
  .entity-eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    margin: 0 0 10px;
    font-family: var(--font-mono);
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-accent);
  }
  .top-flag {
    color: var(--color-accent);
    font-weight: 700;
  }
  .rank-meta {
    color: var(--color-text-muted);
    font-weight: 600;
  }
  /* Theme discoverability hint — sibling to .rank-row, NOT a child. Lives on
     its own line by virtue of being a separate block. Same mono uppercase
     vocabulary as .rank-meta so it reads as a continuation of the kicker
     block without competing with the rank text. */
  .theme-row {
    margin: 0 0 10px;
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .theme-link {
    color: var(--color-text-muted);
    font-weight: 600;
    text-decoration: none;
    transition: color 120ms ease;
  }
  a.theme-link:hover,
  a.theme-link:focus-visible {
    color: var(--color-accent);
    outline: none;
  }
  a.theme-link:focus-visible {
    text-decoration: underline;
    text-underline-offset: 3px;
  }
  .theme-link.static {
    cursor: default;
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
  .byline {
    display: flex;
    flex-wrap: wrap;
    gap: 0 0.5rem;
    margin: 14px 0 16px;
    font-family: var(--font-mono);
    font-size: 11px;
    line-height: 1.5;
    color: var(--color-text-muted);
    letter-spacing: 0.06em;
  }
  .byline-author {
    color: var(--color-text-secondary);
  }
  .byline-sep {
    color: var(--color-border);
  }
  .byline-updated time {
    font-feature-settings: "tnum";
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
