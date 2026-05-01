<script lang="ts">
  import Search from "lucide-svelte/icons/search";
  import Filter from "lucide-svelte/icons/filter";
  import Bookmark from "lucide-svelte/icons/bookmark";
  import type { CatalogTotals } from "$lib/types/publicCatalog.js";
  import StatStrip, { type Stat } from "./StatStrip.svelte";

  interface Props {
    totals: CatalogTotals;
  }

  let { totals }: Props = $props();

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
    <StatStrip {stats} />
  </div>

  <!-- Search + filter row. Search is visual-only in v1 — wires up to a
       global search route in a follow-up. The shape of the input matches
       the mockup so the layout reads correctly today. -->
  <div class="tools-row">
    <label class="search-box">
      <span class="icon"><Search size={16} /></span>
      <input
        type="search"
        placeholder="Search ideas, niches, pain points…"
        aria-label="Search the catalog"
      />
      <span class="kbd" aria-hidden="true">⌘K</span>
    </label>
    <button class="btn-ghost" type="button" disabled aria-disabled="true">
      <Filter size={14} />
      <span>Filter by score</span>
    </button>
    <button class="btn-ghost" type="button" disabled aria-disabled="true">
      <Bookmark size={14} />
      <span>Saved</span>
    </button>
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
  .kbd {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--color-text-muted);
    border: 1px solid var(--color-border-emphasis);
    border-radius: 3px;
    padding: 1px 5px;
    background: var(--color-surface-elevated, #fafafa);
  }
  .btn-ghost {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 7px 12px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    border: 1px solid var(--color-border-emphasis);
    background: var(--color-surface, #fff);
    color: var(--color-text-secondary, var(--color-text-primary));
    cursor: pointer;
    font-family: inherit;
    transition: all 0.12s ease;
  }
  .btn-ghost:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
  .btn-ghost:not(:disabled):hover {
    color: var(--color-text-primary);
    border-color: var(--color-text-muted);
  }
</style>
