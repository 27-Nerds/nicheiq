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
  }

  let { ideas, subNiches = [], defaultView = "grid", showRank = false }: Props = $props();

  // Local interactive state (per scope decision: client-only, no URL sync v1).
  let view = $state<View>(untrack(() => defaultView));
  let sort = $state<SortKey>("opportunity");
  let activeSub = $state<string>("all");

  function scoreFor(idea: IdeaPreview, k: SortKey): number {
    if (k === "demand") return idea.market_fit_score ?? 0;
    if (k === "feasibility") return idea.technical_feasibility_score ?? 0;
    if (k === "opportunity") return idea.seo_scalability_score ?? 0;
    // newest
    return new Date(idea.created_at).getTime();
  }

  const filtered = $derived(
    activeSub === "all"
      ? ideas
      : ideas.filter((i) => i.category?.slug === activeSub),
  );

  const sorted = $derived(
    [...filtered].sort((a, b) => scoreFor(b, sort) - scoreFor(a, sort)),
  );
</script>

{#if subNiches.length > 0}
  <div class="filter-bar">
    <FilterChip
      label="All"
      count={ideas.length}
      active={activeSub === "all"}
      onclick={() => (activeSub = "all")}
    />
    {#each subNiches as s}
      <FilterChip
        label={s.name}
        count={s.ideaCount}
        active={activeSub === s.slug}
        onclick={() => (activeSub = s.slug)}
      />
    {/each}
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
  .filter-bar {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
    padding: 14px 0;
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
