<script lang="ts">
  import StatStrip, { type Stat } from "./StatStrip.svelte";
  import type { NicheContext } from "$lib/types/publicCatalog.js";

  // Page hero for category + sub-category pages. Renders:
  //   H1 + lede + niche-context (industry scope + primary segments) + stats.
  // Optional right-rail aside (CategoryHeroAside / SubcategoryOpportunityPanel)
  // sits beside the prose column on ≥920px.

  interface Props {
    name: string;
    slug: string;
    description?: string | null;
    /** "Sub-niche of X" pill content. Parent context now lives in the
     *  breadcrumb only, so this prop renders nothing today. Kept on the
     *  interface for backward compat with any caller still passing it. */
    parentChip?: { name: string; slug: string } | null;
    /** Reserved — when backend ships growth%, the accent pill can be
     *  re-introduced inline above the H1. Currently unrendered. */
    growthPercent?: number | null;
    /** 4 tiles for the stat strip. Pass null when the page is in empty-research
     *  mode so the strip is suppressed; the parent renders a one-line prose
     *  note in its place. */
    stats?: Stat[] | null;
    /** Niche-context blob; nicheContext.description supersedes `description`
     *  in the lede when present. industryBoundaries renders as a 3-line
     *  clamped paragraph with a "Read more" toggle; marketSegments render
     *  as a 2-column compact list with bullet prefixes — see `.niche-context`
     *  block. */
    nicheContext?: NicheContext | null;
    /** Optional right-rail aside content (e.g. CategoryHeroAside). Renders
     *  to the right of the prose column on ≥768px and stacks below on mobile. */
    aside?: import('svelte').Snippet;
    /** Distinguishes parent-category landing pages from leaf sub-niche pages.
     *  On parent routes, `nicheContext` is sourced from the most-recent
     *  published item's research context (typically a sub-niche), so its
     *  `description` / `industryBoundaries` / `marketSegments` would bleed
     *  sub-niche text onto the parent. When `kind === 'parent'`, prefer the
     *  category's own `description` and suppress nicheContext fields. */
    kind?: 'parent' | 'leaf';
    /** Density of the stat strip. `tiles` (default) renders the 4-tile
     *  StatStrip with first-tile emphasis; `inline` renders a single mono
     *  line with `·` separators — used on sub-niche pages where the right-rail
     *  opportunity panel already carries the heavy stat density. */
    statsVariant?: 'tiles' | 'inline';
    /** Suppress the niche-context block (industry scope + primary segments)
     *  on routes that prefer a focused hero. Sub-niche route passes `false`
     *  to move that supporting copy to a methodology footer below the page.
     *  Default `true` preserves the current parent / PSeo / generic behavior.
     *  Lede logic is unaffected — `nicheContext.description` still flows in. */
    showNicheContext?: boolean;
  }

  let {
    name,
    slug: _slug,
    description = null,
    parentChip: _parentChip = null,
    growthPercent: _growthPercent = null,
    stats = null,
    nicheContext = null,
    aside,
    kind = 'leaf',
    statsVariant = 'tiles',
    showNicheContext = true,
  }: Props = $props();

  // Parent-niche pages append a keyword-tuned suffix to the H1 so the headline
  // reads `"{Category} — Startup Ideas & Pain Points"`. Leaf and programmatic-
  // SEO pages (both default `kind === 'leaf'`) render the bare name so their
  // existing headlines stay unchanged.
  const headline = $derived(
    kind === 'parent' ? `${name} — Startup Ideas & Pain Points` : name,
  );

  // On parent-category pages, prefer the category's own description over the
  // sub-niche's nicheContext.description (which would bleed wrong-niche copy
  // onto the parent). On leaf pages, nicheContext is legitimate and supersedes
  // the shorter category column.
  const lede = $derived(
    kind === 'parent'
      ? (description ?? nicheContext?.description ?? null)
      : (nicheContext?.description ?? description),
  );
  const industryBoundaries = $derived(
    kind === 'parent' || !showNicheContext
      ? null
      : (nicheContext?.industryBoundaries ?? null),
  );
  const marketSegments = $derived(
    kind === 'parent' || !showNicheContext
      ? null
      : (nicheContext?.marketSegments ?? null),
  );

  // 3-line clamp heuristic (~73 chars/line at 13.5px / line-height 1.65 /
  // max-width 640px). False negatives (wraps >3 lines but ≤220 chars) are
  // safe — the clamp class only applies when this is true, so failure mode
  // is "show full text" not "hide content".
  const industryNeedsClamp = $derived(
    (industryBoundaries?.length ?? 0) > 220,
  );
  let industryExpanded = $state(false);
</script>

<header class="page-hero">
  <div class="hero-row">
    <div class="hero-main">
      <h1>{headline}</h1>
      {#if lede}
        <p class="lede">{lede}</p>
      {/if}
      {#if industryBoundaries || (marketSegments && marketSegments.length > 0)}
        <section class="niche-context" aria-label="Niche context">
          {#if industryBoundaries}
            {#key industryBoundaries}
              <div class="nc-block">
                <span class="nc-kicker">Industry</span>
                <div class="nc-prose-wrap" class:clamp={industryNeedsClamp && !industryExpanded}>
                  <p class="nc-prose">{industryBoundaries}</p>
                </div>
                {#if industryNeedsClamp}
                  <button
                    type="button"
                    class="nc-toggle"
                    onclick={() => (industryExpanded = !industryExpanded)}
                    aria-expanded={industryExpanded}
                  >
                    {industryExpanded ? "Show less" : "Read more"}
                  </button>
                {/if}
              </div>
            {/key}
          {/if}
          {#if marketSegments && marketSegments.length > 0}
            <div class="nc-block">
              <span class="nc-kicker">
                Primary segments
                <span class="nc-kicker-sep" aria-hidden="true">·</span>
                <span class="nc-kicker-count">{marketSegments.length}</span>
              </span>
              <ul class="nc-segments">
                {#each marketSegments as seg, i (seg)}
                  <li
                    class="nc-seg catalog-fade-in"
                    style:animation-delay={`${Math.min(i, 5) * 0.06}s`}
                    title={seg}
                  >
                    <span class="nc-bullet" aria-hidden="true">·</span>
                    <span class="nc-text">{seg}</span>
                  </li>
                {/each}
              </ul>
            </div>
          {/if}
        </section>
      {/if}
      <!-- Inline stats sit immediately under the lede / niche-context so the
           line stays tied to the description column instead of floating below
           the right-rail aside. The tiles variant is full-width and renders
           outside .hero-row below. -->
      {#if stats && stats.length > 0 && statsVariant === 'inline'}
        <div class="quick-stats">
          {#each stats as s, i}
            {#if i > 0}<span class="dot-sep">·</span>{/if}
            <span class="qs-stat">
              <b>{s.value}</b> {s.label}
            </span>
          {/each}
        </div>
      {/if}
    </div>
    {#if aside}
      <aside class="hero-aside">{@render aside()}</aside>
    {/if}
  </div>
  {#if stats && stats.length > 0 && statsVariant === 'tiles'}
    <div class="strip-wrap">
      <StatStrip {stats} emphasis />
    </div>
  {/if}
</header>

<style>
  .page-hero {
    padding: 32px 0;
  }
  /* Flex hero with optional right aside. Stacks on narrow viewports. */
  .hero-row {
    display: flex;
    gap: 32px;
    align-items: flex-start;
  }
  .hero-main {
    flex: 1 1 auto;
    min-width: 0;
  }
  .hero-aside {
    flex: 0 0 360px;
    min-width: 0;
  }
  @media (max-width: 920px) {
    .hero-row {
      flex-direction: column;
    }
    .hero-aside {
      flex-basis: auto;
      width: 100%;
    }
  }
  h1 {
    margin: 6px 0 14px;
    font-size: 40px;
    font-weight: 600;
    letter-spacing: -0.03em;
    line-height: 1.05;
    color: var(--color-text-primary);
    text-wrap: balance;
  }
  .lede {
    font-size: 15px;
    color: var(--color-text-secondary, var(--color-text-primary));
    line-height: 1.6;
    max-width: 620px;
    margin: 0 0 16px;
  }
  /* Niche-context block — quiet editorial treatment for industry scope and
     primary market segments. Replaces the prior chip-based `.boundary-row`
     layout. Mono kickers + body text for scope, mono-numbered list for
     segments. No cards / pills / per-row borders besides hairline dividers. */
  .niche-context {
    display: flex;
    flex-direction: column;
    gap: 22px;
    margin: 0 0 24px;
  }
  .nc-block {
    min-width: 0;
  }
  /* Block-level kicker — vertical margin behaves predictably here unlike
     inline-flex. Letter-spacing 0.08em matches the .theme-num / .dt-label
     kicker family used elsewhere in the catalog. */
  .nc-kicker {
    display: block;
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 600;
    color: var(--color-accent-muted);
    margin: 0 0 8px;
  }
  .nc-kicker-sep {
    opacity: 0.55;
    margin: 0 4px;
  }
  .nc-kicker-count {
    color: var(--color-text-secondary);
  }
  .nc-prose-wrap {
    position: relative;
  }
  .nc-prose-wrap.clamp .nc-prose {
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 3;
    line-clamp: 3;
    overflow: hidden;
  }
  .nc-prose {
    font-size: 13.5px;
    line-height: 1.65;
    color: var(--color-text-secondary, var(--color-text-primary));
    max-width: 640px;
    margin: 0;
    overflow-wrap: anywhere;
  }
  .nc-toggle {
    display: inline-block;
    margin-top: 6px;
    padding: 4px 0;
    background: none;
    border: none;
    cursor: pointer;
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--color-text-muted);
    text-decoration: none;
    transition: color 0.12s;
  }
  .nc-toggle:hover {
    color: var(--color-text-primary);
  }
  .nc-toggle:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .nc-segments {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    column-gap: 24px;
    row-gap: 4px;
  }
  .nc-seg {
    display: grid;
    grid-template-columns: 12px 1fr;
    gap: 8px;
    align-items: baseline;
    padding: 4px 0;
  }
  .nc-bullet {
    font-family: var(--font-mono);
    color: var(--color-accent-muted, rgba(154, 52, 18, 0.7));
    font-size: 14px;
    line-height: 1;
    align-self: center;
  }
  .nc-text {
    font-size: 13px;
    line-height: 1.5;
    color: var(--color-text-primary);
    overflow-wrap: anywhere;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    overflow: hidden;
  }
  @media (max-width: 640px) {
    .nc-segments {
      grid-template-columns: 1fr;
    }
    .nc-prose {
      font-size: 13.5px;
    }
    .nc-text {
      font-size: 12.5px;
      -webkit-line-clamp: 3;
      line-clamp: 3;
    }
  }
  .strip-wrap {
    margin-top: 28px;
  }
  /* Inline mono stat line — used on sub-niche pages where the right-rail
     opportunity panel already carries primary stat density. */
  .quick-stats {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    margin-top: 22px;
    font-family: var(--font-mono);
    font-size: 13px;
    color: var(--color-text-muted);
  }
  .quick-stats b {
    color: var(--color-text-primary);
    font-weight: 600;
    font-size: 14px;
  }
  .quick-stats .dot-sep {
    color: var(--color-text-muted);
    opacity: 0.5;
  }
</style>
