<script lang="ts">
  import ChevronRight from "lucide-svelte/icons/chevron-right";
  import IconBadge from "./IconBadge.svelte";
  import { categoryIcon } from "$lib/utils/categoryIcons";
  import { categoryPath } from "$lib/utils/urls";
  import type { CategoryLandingChild } from "$lib/types/catalog-landing.js";

  // Two-tier sub-niche directory for /ideas/[niche] §04. Splits children by
  // research density (`ideaCount + painPointCount > 0`):
  //   Researched → rich card grid (icon, name, counts, description)
  //   Atlas      → quiet dot-separated link list ("Also in this category")
  // Replaces the prior flat SubNicheCell grid, which gave placeholder rows
  // the same visual weight as researched ones (~92% of cells were empty).

  interface Props {
    subNiches: CategoryLandingChild[];
    parentSlug: string;
  }

  let { subNiches, parentSlug }: Props = $props();

  function density(c: CategoryLandingChild): number {
    return (c.ideaCount ?? 0) + (c.painPointCount ?? 0);
  }

  function pluralLabel(n: number, singular: string, plural?: string): string {
    return n === 1 ? singular : (plural ?? `${singular}s`);
  }

  const researched = $derived(
    [...subNiches]
      .filter((c) => density(c) > 0)
      .sort((a, b) => {
        const dd = density(b) - density(a);
        return dd !== 0 ? dd : a.name.localeCompare(b.name);
      }),
  );
  const atlas = $derived(
    [...subNiches]
      .filter((c) => density(c) === 0)
      .sort((a, b) => a.name.localeCompare(b.name)),
  );
  // Min-2-digit zero-padded indices (01, 02 … N). Editorial flair plus
  // a fixed leading-column width so names hang from one baseline.
  const atlasIdxPad = $derived(Math.max(2, String(atlas.length).length));
</script>

<div class="dir">
  {#if researched.length > 0}
    <div class="tier">
      <header class="tier-head">
        <span class="tier-kicker tier-kicker--accent">Researched</span>
        <span class="tier-meta">sorted by density</span>
      </header>
      <ul class="card-grid">
        {#each researched as sub (sub.id)}
          {@const Icon = categoryIcon(sub.slug)}
          <li>
            <a
              class="card"
              href={categoryPath({ slug: sub.slug, parentSlug })}
              data-sveltekit-preload-data="hover"
            >
              <span class="card-icon">
                <IconBadge size={26}>
                  <Icon size={14} />
                </IconBadge>
              </span>
              <h3 class="card-title">{sub.name}</h3>
              <span class="card-arrow"><ChevronRight size={14} /></span>
              <div class="card-meta">
                <span class="num">{sub.ideaCount.toLocaleString()}</span>
                <span class="lbl">{pluralLabel(sub.ideaCount, "idea")}</span>
                <span class="dot" aria-hidden="true">·</span>
                <span class="num">{sub.painPointCount.toLocaleString()}</span>
                <span class="lbl">
                  {pluralLabel(sub.painPointCount, "pain point")}
                </span>
              </div>
              {#if sub.description}
                <p class="card-desc">{sub.description}</p>
              {/if}
            </a>
          </li>
        {/each}
      </ul>
    </div>
  {/if}

  {#if atlas.length > 0}
    <div class="tier tier--atlas" class:tier--solo={researched.length === 0}>
      <header class="tier-head">
        <span class="tier-kicker">
          {researched.length > 0 ? "Also in this category" : "Mapped"}
        </span>
        <span class="tier-meta">
          {atlas.length}
          {pluralLabel(atlas.length, "sub-niche")}
        </span>
      </header>
      <ol class="atlas-list">
        {#each atlas as sub, i (sub.id)}
          <li class="atlas-item">
            <a
              class="atlas-link"
              href={categoryPath({ slug: sub.slug, parentSlug })}
              data-sveltekit-preload-data="hover"
            >
              <span class="atlas-idx">
                {String(i + 1).padStart(atlasIdxPad, "0")}
              </span>
              <span class="atlas-name">{sub.name}</span>
              <span class="atlas-arrow" aria-hidden="true">→</span>
            </a>
          </li>
        {/each}
      </ol>
      <!-- "Research pending" now lives in the section divider's metaText on
           the consuming page — a trailing widow line under a 51-row list
           floated unanchored. -->
    </div>
  {/if}
</div>

<style>
  .dir {
    display: flex;
    flex-direction: column;
    gap: 28px;
  }

  /* Tier shell — kicker row above content. The atlas tier carries a dashed
     top rule when it follows a researched tier, telegraphing the demotion in
     editorial weight. Solo-atlas case drops the rule. */
  .tier {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .tier--atlas {
    padding-top: 20px;
    border-top: 1px dashed var(--color-border);
  }
  .tier--atlas.tier--solo {
    padding-top: 0;
    border-top: none;
  }
  .tier-head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 1rem;
  }
  .tier-kicker {
    font-family: var(--font-mono);
    font-size: 10px;
    line-height: 1;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 700;
    color: var(--color-text-muted);
  }
  .tier-kicker--accent {
    color: var(--color-accent-muted, var(--color-text-muted));
  }
  .tier-meta {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--color-text-muted);
    font-feature-settings: "tnum" 1;
  }

  /* Researched card grid — `min(100%, 360px)` floor lets a single card collapse
     to the viewport width on narrow screens, instead of overflowing the
     catalog-shell padding when the 360px floor would push past the edge. */
  .card-grid {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 360px), 1fr));
    gap: 12px;
  }
  .card-grid > li {
    list-style: none;
  }
  .card {
    display: grid;
    grid-template-columns: auto 1fr auto;
    column-gap: 10px;
    row-gap: 8px;
    align-items: center;
    background: var(--color-surface, #fff);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    padding: 14px 16px;
    text-decoration: none;
    color: inherit;
    transition: border-color 0.12s ease;
  }
  .card:hover {
    border-color: var(--color-border-emphasis);
  }
  .card:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
    border-color: transparent;
  }
  .card-icon {
    display: inline-flex;
    flex-shrink: 0;
    grid-row: 1;
  }
  .card-title {
    grid-row: 1;
    margin: 0;
    font-size: 15px;
    font-weight: 600;
    letter-spacing: -0.01em;
    color: var(--color-text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    transition: color 0.12s ease;
  }
  .card:hover .card-title {
    color: var(--color-accent);
  }
  .card-arrow {
    grid-row: 1;
    color: var(--color-text-muted);
    display: inline-flex;
    transition:
      transform 0.12s ease,
      color 0.12s ease;
  }
  .card:hover .card-arrow {
    color: var(--color-accent);
    transform: translateX(2px);
  }
  /* Meta + description span the full card width so they don't offset under
     the title column. */
  .card-meta {
    grid-column: 1 / -1;
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.04em;
    color: var(--color-text-muted);
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 4px;
  }
  .num {
    color: var(--color-text-primary);
    font-weight: 700;
    font-feature-settings: "tnum" 1, "calt" 1;
  }
  .lbl {
    color: var(--color-text-muted);
  }
  .dot {
    color: var(--color-text-muted);
    opacity: 0.55;
    margin: 0 2px;
  }
  .card-desc {
    grid-column: 1 / -1;
    margin: 0;
    font-size: 13px;
    line-height: 1.55;
    color: var(--color-text-secondary, var(--color-text-primary));
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  /* Atlas — slim numbered rows on dashed hairlines. Adopts the same
     dashed-border + mono-kicker editorial vocabulary used by DataRow
     and the tier separator above, so the section reads as one family.
     Two-column CSS grid with `gap: 0` lets the per-cell dashed
     bottom-borders touch across the column division and read as a
     continuous ruled-paper line, one stripe per visual row. */
  .atlas-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    /* dashed hairline at the top doubles as the section's first row-rule */
    border-top: 1px dashed var(--color-border);
  }
  .atlas-item {
    list-style: none;
    border-bottom: 1px dashed var(--color-border);
    min-width: 0;
  }
  .atlas-link {
    display: grid;
    grid-template-columns: auto 1fr auto;
    column-gap: 14px;
    align-items: center;
    padding: 11px 12px 11px 6px;
    color: inherit;
    text-decoration: none;
    min-width: 0;
  }
  .atlas-link:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: -2px;
    border-radius: 2px;
  }
  .atlas-idx {
    font-family: var(--font-mono);
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.08em;
    color: var(--color-accent-muted);
    font-feature-settings: "tnum" 1;
    /* fixed width keeps names hanging from the same baseline regardless
       of single- vs double-digit indices */
    min-width: 2.25em;
  }
  .atlas-name {
    font-size: 13px;
    font-weight: 500;
    color: var(--color-text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    letter-spacing: -0.005em;
    transition: color 0.12s ease;
    min-width: 0;
  }
  .atlas-link:hover .atlas-name {
    color: var(--color-accent);
  }
  .atlas-arrow {
    font-family: var(--font-mono);
    font-size: 14px;
    line-height: 1;
    color: var(--color-text-muted);
    opacity: 0.5;
    transition:
      transform 0.12s ease,
      color 0.12s ease,
      opacity 0.12s ease;
  }
  .atlas-link:hover .atlas-arrow {
    color: var(--color-accent);
    opacity: 1;
    transform: translateX(2px);
  }
  /* Mobile collapses to single column; the lone last item then sits below
     the rest naturally without the half-width hairline issue. */
  @media (max-width: 640px) {
    .atlas-list {
      grid-template-columns: 1fr;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .card,
    .card-title,
    .card-arrow,
    .atlas-name,
    .atlas-arrow {
      transition: none;
    }
  }
</style>
