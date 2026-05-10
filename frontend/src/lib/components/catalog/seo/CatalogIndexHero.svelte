<script lang="ts">
  import Search from "lucide-svelte/icons/search";
  import Bookmark from "lucide-svelte/icons/bookmark";
  import Rocket from "lucide-svelte/icons/rocket";
  import { page } from "$app/state";
  import type { CatalogTotals } from "$lib/types/publicCatalog.js";

  interface Props {
    totals: CatalogTotals;
    /** Two-way bound search query, lifted to /ideas/+page.svelte for filtering. */
    query?: string;
    /** Hero primary CTA href — same target as the bottom-of-page "Run your
     *  own research" link. Optional: hides the CTA when null/undefined. */
    ctaHref?: string | null;
  }

  let { totals, query = $bindable(""), ctaHref = null }: Props = $props();

  // Authenticated visitors get a direct link; anonymous visitors land at login
  // first (the /ideas/saved route is under (app) which redirects unauth users
  // with returnTo=/ideas/saved). Either way, /ideas/saved is the canonical
  // href — the route was nested under /ideas because saved items are catalog
  // content (ideas + pain points), so the URL hierarchy mirrors that.
  const session = $derived(page.data.session);
  const savedHref = $derived(
    session?.user ? "/ideas/saved" : "/login?returnTo=/ideas/saved",
  );

  // Defensive date parsing — old Redis cache entries may pre-date the
  // `lastUpdated` field (undefined), and a corrupted ISO string falls back
  // to "now" so the kicker always renders something sensible.
  const datelineMonth = $derived.by(() => {
    let d = totals.lastUpdated ? new Date(totals.lastUpdated) : new Date();
    if (Number.isNaN(d.getTime())) d = new Date();
    return new Intl.DateTimeFormat("en-US", {
      month: "long",
      year: "numeric",
    }).format(d).toUpperCase();
  });

  // Compact thousands formatter for `contentItemsMined` (e.g. 19,847 → 19.8K).
  function compact(n: number): string {
    if (n >= 1000) return `${(n / 1000).toFixed(1).replace(/\.0$/, "")}K`;
    return n.toLocaleString();
  }
</script>

<header class="page-hero">
  <!-- Editorial dateline kicker — replaces the 4-tile StatStrip. Single
       mono row carrying month/year + the three most-meaningful counts.
       Wraps gracefully on narrow viewports via flex-wrap on .kicker. -->
  <div class="kicker" aria-label="Catalog edition statistics">
    <span class="k-edition">EDITION · {datelineMonth}</span>
    <span class="k-dot" aria-hidden="true">·</span>
    <span class="k-stat"><span class="k-num">{totals.totalIdeas.toLocaleString()}</span> IDEAS</span>
    <span class="k-dot" aria-hidden="true">·</span>
    <span class="k-stat"><span class="k-num">{totals.totalCategories.toLocaleString()}</span> CATEGORIES</span>
    <span class="k-dot" aria-hidden="true">·</span>
    <span class="k-stat"><span class="k-num">{compact(totals.contentItemsMined)}</span> DISCUSSIONS MINED</span>
  </div>

  <h1>Startup Ideas <span class="accent">&</span> Validated Pain Points</h1>
  <p class="lede">
    Hand-curated startup ideas and validated pain points, scored on demand,
    feasibility, and SEO opportunity.
  </p>

  <!-- Catalog search + run-research CTA + Saved link. Search query is URL-synced
       in the parent route (?q=...). Saved link goes to /saved (auth-gated). -->
  <div class="tools-row">
    <label class="search-box">
      <span class="icon"><Search size={16} /></span>
      <input
        type="search"
        placeholder="Search niches and sub-niches…"
        aria-label="Search the catalog"
        bind:value={query}
      />
    </label>
    {#if ctaHref}
      <a class="btn-cta-primary" href={ctaHref} data-sveltekit-preload-data="hover">
        <Rocket size={15} />
        <span>Run your own research</span>
      </a>
    {/if}
    <a class="saved-link" href={savedHref} data-sveltekit-preload-data="hover">
      <Bookmark size={14} />
      <span>Saved</span>
    </a>
  </div>
</header>

<style>
  .page-hero {
    padding: 40px 0 28px;
    border-bottom: 1px solid var(--color-border);
    margin-bottom: 28px;
  }
  /* Mono editorial dateline — replaces the StatStrip. Same kicker tokens
     used by SectionDivider so the catalog's "almanac" voice carries from
     section dividers up to the page hero. flex-wrap lets it gracefully
     break onto multiple lines on narrow viewports. */
  .kicker {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 8px 10px;
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    font-weight: 600;
    margin: 0 0 18px;
  }
  .k-edition {
    color: var(--color-accent);
    font-weight: 700;
  }
  .k-dot {
    color: var(--color-text-muted);
    opacity: 0.55;
  }
  .k-stat {
    color: var(--color-text-muted);
  }
  .k-num {
    color: var(--color-text-primary);
    font-weight: 700;
    font-feature-settings: "tnum" 1, "calt" 1;
  }
  h1 {
    font-weight: 600;
    font-size: 36px;
    line-height: 1.1;
    letter-spacing: -0.025em;
    margin: 0 0 14px;
    max-width: 840px;
    color: var(--color-text-primary);
  }
  .accent {
    color: var(--color-accent);
  }
  .lede {
    font-size: 15px;
    line-height: 1.6;
    color: var(--color-text-secondary, var(--color-text-primary));
    max-width: 620px;
    margin: 0 0 24px;
  }
  .tools-row {
    display: flex;
    gap: 10px;
    margin-top: 18px;
    flex-wrap: wrap;
    align-items: center;
  }
  .search-box {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    border: 1px solid var(--color-border);
    border-radius: 8px;
    background: var(--color-surface, #fff);
    transition: all 0.12s ease;
    flex: 1;
    min-width: 280px;
    max-width: 520px;
  }
  .search-box:focus-within {
    border-color: var(--color-text-primary);
    box-shadow: 0 0 0 3px rgba(0, 0, 0, 0.04);
  }
  .search-box .icon {
    color: var(--color-text-muted);
    display: inline-flex;
    flex-shrink: 0;
  }
  .search-box input {
    flex: 1;
    border: none;
    outline: none;
    background: transparent;
    font-size: 14px;
    color: var(--color-text-primary);
    font-family: inherit;
  }
  .search-box input::placeholder {
    color: var(--color-text-muted);
    opacity: 0.7;
  }

  /* Primary CTA — accent button, kept narrow so the search box gets
     priority width. flex-shrink: 0 prevents this from being squeezed
     when the search box claims its full max-width. */
  .btn-cta-primary {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 10px 16px;
    border-radius: 8px;
    font-size: 13.5px;
    font-weight: 600;
    background: var(--color-accent);
    color: var(--color-surface, #fff);
    text-decoration: none;
    border: 1px solid transparent;
    flex-shrink: 0;
    white-space: nowrap;
    transition:
      background-color 140ms ease,
      box-shadow 140ms ease,
      transform 140ms ease;
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.18),
      0 1px 2px rgba(154, 52, 18, 0.18);
  }
  .btn-cta-primary:hover {
    background: var(--color-accent-hover, var(--color-accent-dark));
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.22),
      0 2px 4px rgba(154, 52, 18, 0.22);
  }
  .btn-cta-primary:active {
    transform: scale(0.98);
  }
  .btn-cta-primary:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  /* Saved link — ghost button next to the search box. Matches the catalog's
     line-bordered button vocabulary (1px border, hairline hover state, no
     shadow). */
  .saved-link {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 10px 14px;
    border: 1px solid var(--color-border);
    border-radius: 8px;
    background: var(--color-surface, #fff);
    font-size: 13px;
    font-weight: 500;
    color: var(--color-text-secondary, var(--color-text-primary));
    text-decoration: none;
    white-space: nowrap;
    flex-shrink: 0;
    transition:
      color 0.12s ease,
      border-color 0.12s ease,
      background 0.12s ease;
  }
  .saved-link:hover {
    color: var(--color-text-primary);
    border-color: var(--color-border-emphasis);
    background: var(--color-bg-base, #fafafa);
  }
  .saved-link:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
</style>
