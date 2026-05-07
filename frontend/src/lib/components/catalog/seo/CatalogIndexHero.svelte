<script lang="ts">
  import Search from "lucide-svelte/icons/search";
  import Bookmark from "lucide-svelte/icons/bookmark";
  import { page } from "$app/state";
  import type { CatalogTotals } from "$lib/types/publicCatalog.js";
  import StatStrip, { type Stat } from "./StatStrip.svelte";

  interface Props {
    totals: CatalogTotals;
    /** Two-way bound search query, lifted to /ideas/+page.svelte for filtering. */
    query?: string;
  }

  let { totals, query = $bindable("") }: Props = $props();

  // Authenticated visitors get a direct link; anonymous visitors land at login
  // first (the /saved route is under (app) which redirects unauth users with
  // returnTo=/saved). Either way, /saved is the canonical href.
  const session = $derived(page.data.session);
  const savedHref = $derived(
    session?.user ? "/saved" : "/login?returnTo=/saved",
  );

  const stats = $derived<Stat[]>([
    { value: totals.totalIdeas.toLocaleString(), label: "Ideas tracked" },
    { value: totals.totalCategories.toLocaleString(), label: "Categories" },
    { value: totals.totalSubcategories.toLocaleString(), label: "Sub-niches" },
    {
      value:
        totals.contentItemsMined >= 1000
          ? `${(totals.contentItemsMined / 1000).toFixed(1).replace(/\.0$/, "")}K`
          : totals.contentItemsMined.toLocaleString(),
      label: "Sources mined",
      tone: "amber",
    },
  ]);
</script>

<header class="page-hero">
  <h1>Startup Ideas <span class="accent">&</span> Validated Pain Points</h1>
  <p class="lede">
    Hand-curated and AI-sourced from real Reddit and Hacker News discussions —
    scored on demand, technical feasibility, and SEO opportunity. Updated
    weekly.
  </p>

  <div class="strip-wrap">
    <StatStrip {stats} emphasis />
  </div>

  <!-- Catalog search + Saved link. Search query is URL-synced in the parent
       route (?q=...). Saved link goes to /saved (auth-gated). -->
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
    <a class="saved-link" href={savedHref} data-sveltekit-preload-data="hover">
      <Bookmark size={14} />
      <span>Saved</span>
    </a>
  </div>
</header>

<style>
  .page-hero {
    padding: 48px 0 32px;
    border-bottom: 1px solid var(--color-border);
    margin-bottom: 32px;
  }
  h1 {
    font-weight: 600;
    font-size: 36px;
    line-height: 1.1;
    letter-spacing: -0.025em;
    margin: 10px 0 14px;
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
    margin: 0 0 28px;
  }
  .strip-wrap {
    margin-top: 28px;
  }
  .tools-row {
    display: flex;
    gap: 10px;
    margin-top: 20px;
    flex-wrap: wrap;
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

  /* Saved link — ghost button next to the search box. Matches the catalog's
     line-bordered button vocabulary (1px border, hairline hover state, no
     shadow). Mirrors page-index.jsx:55 in the ideas-v2 design. */
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
