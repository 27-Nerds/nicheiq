<script lang="ts">
  import { untrack } from "svelte";
  import Grid from "lucide-svelte/icons/layout-grid";
  import List from "lucide-svelte/icons/list";
  import type { IdeaPreview, CategoryLandingChild } from "$lib/types/catalog-landing.js";
  import IdeaCardV2 from "./IdeaCardV2.svelte";
  import FilterChip from "./FilterChip.svelte";
  import TriLegend from "./TriLegend.svelte";
  import IdeasListTable from "./IdeasListTable.svelte";

  // "Browse all ideas" coordinator — filter chips, sort + view toggle, then
  // either grid (<IdeaCardV2>) or list (<IdeasListTable>) view.
  // State is local; no URL sync v1.
  //
  // Filter chips:
  //   [Top] (default) — top N by current sort
  //   [All]           — full set
  //   [<sub-niche>]   — per-sub-niche filter (one chip per child)
  // Phase 2 of the IA cleanup: this section is the canonical "all ideas" home
  // (the separate "Top ideas in {category}" teaser was retired). The "Top"
  // filter restores the teaser-like default landing without a separate section.

  type SortKey = "opportunity" | "demand" | "feasibility" | "newest";
  type View = "grid" | "list";

  interface Props {
    ideas: IdeaPreview[];
    /** Sub-niche children for the chip filter row. Empty array hides the chips. */
    subNiches?: CategoryLandingChild[];
    /** Initial view mode. Sub-niche routes pass `"list"` to render the anchor
     *  table per the catalog v2 mock; default `"grid"` preserves category page
     *  behavior. User can still toggle either way after mount. */
    defaultView?: View;
    /** Render a numeric rank prefix in list view (Option A: sub-page only).
     *  Rank reflects visible sorted/filtered position, not absolute idea rank.
     *  Hidden in grid view regardless. */
    showRank?: boolean;
    /** Default-active filter. `"top"` shows top-N by current sort; `"all"`
     *  shows the full set. Sub-niche pages skip the chip row entirely (no
     *  subNiches passed) so they default to "all" effectively. */
    defaultFilter?: "top" | "all";
  }

  const TOP_LIMIT = 5;

  let {
    ideas,
    subNiches = [],
    defaultView = "grid",
    showRank = false,
    defaultFilter = "top",
  }: Props = $props();

  // Local interactive state (per scope decision: client-only, no URL sync v1).
  let view = $state<View>(untrack(() => defaultView));
  let sort = $state<SortKey>("opportunity");
  let activeSub = $state<string>(untrack(() => defaultFilter));

  function scoreFor(idea: IdeaPreview, k: SortKey): number {
    if (k === "demand") return idea.market_fit_score ?? 0;
    if (k === "feasibility") return idea.technical_feasibility_score ?? 0;
    if (k === "opportunity") return idea.seo_scalability_score ?? 0;
    // newest
    return new Date(idea.created_at).getTime();
  }

  // Filter: "top" + "all" share the full set; sub-niche chips filter by slug.
  const filtered = $derived(
    activeSub === "top" || activeSub === "all"
      ? ideas
      : ideas.filter((i) => i.category?.slug === activeSub),
  );

  const sortedAll = $derived(
    [...filtered].sort((a, b) => scoreFor(b, sort) - scoreFor(a, sort)),
  );

  // "Top" caps to TOP_LIMIT after sort. All other filters render the full
  // sorted list — caller-controlled subset.
  const sorted = $derived(
    activeSub === "top" ? sortedAll.slice(0, TOP_LIMIT) : sortedAll,
  );

  // Two-axis filter row: scope (Top/All) is a segmented control; sub-niche is
  // a chip row. Each axis only renders when it carries meaning, and the
  // VIEW / SUB-NICHE kickers only appear when both axes coexist (otherwise
  // the kicker is noise above a single control).
  const hasScopeToggle = $derived(
    subNiches.length > 0 || ideas.length > TOP_LIMIT,
  );
  const showAxisKickers = $derived(hasScopeToggle && subNiches.length > 0);
</script>

{#if hasScopeToggle || subNiches.length > 0}
  <div class="filter-bar">
    {#if hasScopeToggle}
      <div class="filter-axis">
        {#if showAxisKickers}
          <span class="filter-kicker">View</span>
        {/if}
        <div class="scope-toggle" role="group" aria-label="Idea scope">
          <button
            type="button"
            class:active={activeSub === "top"}
            onclick={() => (activeSub = "top")}
            aria-pressed={activeSub === "top"}
          >
            <span>Top</span>
            <span class="scope-count">{Math.min(TOP_LIMIT, ideas.length)}</span>
          </button>
          <button
            type="button"
            class:active={activeSub === "all"}
            onclick={() => (activeSub = "all")}
            aria-pressed={activeSub === "all"}
          >
            <span>All</span>
            <span class="scope-count">{ideas.length}</span>
          </button>
        </div>
      </div>
    {/if}
    {#if subNiches.length > 0}
      <div class="filter-axis">
        {#if showAxisKickers}
          <span class="filter-kicker">Sub-niche</span>
        {/if}
        <div class="chip-row">
          {#each subNiches as s}
            <FilterChip
              label={s.name}
              count={s.ideaCount}
              active={activeSub === s.slug}
              onclick={() => (activeSub = s.slug)}
            />
          {/each}
        </div>
      </div>
    {/if}
  </div>
{/if}

<div class="toolbar">
  <div class="left">
    <span class="count">
      Showing <strong>{sorted.length}</strong>
      {sorted.length === 1 ? "idea" : "ideas"}
    </span>
    <TriLegend />
  </div>
  <div class="right">
    <label class="sort-label">
      <span class="sort-text">Sort by</span>
      <select bind:value={sort}>
        <option value="opportunity">Opportunity score</option>
        <option value="demand">Demand score</option>
        <option value="feasibility">Feasibility score</option>
        <option value="newest">Newest</option>
      </select>
    </label>
    <div class="view-toggle">
      <button
        type="button"
        class:active={view === "grid"}
        onclick={() => (view = "grid")}
        aria-label="Grid view"
      >
        <Grid size={13} />
      </button>
      <button
        type="button"
        class:active={view === "list"}
        onclick={() => (view = "list")}
        aria-label="List view"
      >
        <List size={13} />
      </button>
    </div>
  </div>
</div>

{#if view === "grid"}
  <div class="ideas-grid">
    {#each sorted as idea}
      <IdeaCardV2 {idea} subLabel={idea.category?.name ?? null} />
    {/each}
  </div>
{:else}
  <IdeasListTable ideas={sorted} {showRank} />
{/if}

<style>
  /* Two-axis filter row. Scope (Top/All) is a segmented control; sub-niche is
     a chip row. Each axis is a column block — kicker above controls — so
     both axes share the same shape regardless of how their controls wrap.
     Kickers ("View", "Sub-niche") only appear when both axes coexist. */
  .filter-bar {
    display: flex;
    align-items: flex-start;
    gap: 16px;
    flex-wrap: wrap;
    padding: 10px 0;
  }
  .filter-axis {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 6px;
    min-width: 0;
  }
  /* Mono kicker — same family used for `.nc-kicker`, `.theme-num`, etc.
     `line-height: 1` is critical: default `normal` adds ~4px of baseline space
     below the glyph that varies with font, making the kicker→control gap
     visually unequal between axes. Pinning to 1 normalizes both axes. */
  .filter-kicker {
    font-family: var(--font-mono);
    font-size: 10px;
    line-height: 1;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 700;
    color: var(--color-text-muted);
    white-space: nowrap;
  }
  /* Segmented scope toggle — mirrors `.view-toggle` (grid/list switch) below
     so the page reads as one consistent system. */
  .scope-toggle {
    display: inline-flex;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    overflow: hidden;
  }
  .scope-toggle button {
    padding: 5px 11px;
    border: none;
    background: transparent;
    color: var(--color-text-secondary, var(--color-text-primary));
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-family: inherit;
    font-size: 12px;
    line-height: 1;
    transition: background-color 0.12s, color 0.12s;
  }
  .scope-toggle button + button {
    border-left: 1px solid var(--color-border);
  }
  .scope-toggle button:hover:not(.active) {
    color: var(--color-text-primary);
  }
  .scope-toggle button.active {
    background: var(--color-text-primary);
    color: var(--color-bg-elevated, #fff);
  }
  .scope-toggle button:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .scope-count {
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.04em;
    opacity: 0.8;
  }
  .chip-row {
    display: inline-flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: center;
    min-width: 0;
  }
  @media (max-width: 768px) {
    .filter-bar {
      flex-direction: column;
      gap: 16px;
    }
    .filter-axis {
      width: 100%;
    }
  }
  .toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 0 20px;
    border-top: 1px solid var(--color-border);
    gap: 16px;
    flex-wrap: wrap;
  }
  .left {
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
  }
  .count {
    font-size: 13px;
    color: var(--color-text-muted);
    white-space: nowrap;
  }
  .count strong {
    color: var(--color-text-primary);
    font-weight: 600;
  }
  .right {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }
  .sort-label {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .sort-text {
    font-size: 12px;
    color: var(--color-text-muted);
  }
  select {
    border: 1px solid var(--color-border);
    border-radius: 6px;
    padding: 5px 11px;
    background: var(--color-bg-elevated, #fff);
    color: var(--color-text-primary);
    font-family: inherit;
    font-size: 12px;
    cursor: pointer;
  }
  .view-toggle {
    display: flex;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    overflow: hidden;
  }
  .view-toggle button {
    padding: 5px 10px;
    border: none;
    background: var(--color-bg-elevated, #fff);
    color: var(--color-text-secondary, var(--color-text-primary));
    cursor: pointer;
    display: inline-flex;
    align-items: center;
  }
  .view-toggle button + button {
    border-left: 1px solid var(--color-border);
  }
  .view-toggle button.active {
    background: var(--color-text-primary);
    color: var(--color-bg-elevated, #fff);
  }
  .ideas-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 12px;
    margin-bottom: 48px;
  }
</style>
