<script lang="ts">
  import Grid from "lucide-svelte/icons/layout-grid";
  import List from "lucide-svelte/icons/list";
  import type { IdeaPreview, CategoryLandingChild } from "$lib/types/catalog-landing.js";
  import IdeaCardV2 from "./IdeaCardV2.svelte";
  import FilterChip from "./FilterChip.svelte";
  import TriLegend from "./TriLegend.svelte";
  import VerdictBadge from "./VerdictBadge.svelte";
  import Trifecta from "./Trifecta.svelte";
  import { ideaPath } from "$lib/utils/urls";
  import { solutionDisplayTitle, solutionCardDescription } from "$lib/utils/solution-utils.js";

  // "Browse all ideas" with sub-niche chip filters, sort dropdown, and
  // grid↔list view toggle. State is local — no URL sync (deferred).

  interface Props {
    ideas: IdeaPreview[];
    /** Sub-niche children for the chip filter row. Empty array hides the chips. */
    subNiches?: CategoryLandingChild[];
  }

  let { ideas, subNiches = [] }: Props = $props();

  type SortKey = "opportunity" | "demand" | "feasibility" | "newest";
  type View = "grid" | "list";

  // Local interactive state (per scope decision: client-only, no URL sync v1).
  let view = $state<View>("grid");
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

  function toScores(idea: IdeaPreview) {
    return {
      demand: idea.market_fit_score == null ? null : idea.market_fit_score * 100,
      feasibility:
        idea.technical_feasibility_score == null
          ? null
          : idea.technical_feasibility_score * 100,
      opportunity:
        idea.seo_scalability_score == null ? null : idea.seo_scalability_score * 100,
    };
  }
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
  <div class="ideas-list">
    <div class="list-head">
      <span>Idea</span>
      <span>Sub-niche</span>
      <span>Scores (D / F / O)</span>
      <span>Verdict</span>
    </div>
    {#each sorted as idea}
      <a class="list-row" href={ideaPath(idea.slug)}>
        <div class="cell-idea">
          <div class="idea-title">{solutionDisplayTitle(idea)}</div>
          <div class="idea-tagline">{solutionCardDescription(idea)}</div>
        </div>
        <div class="cell-sub">{idea.category?.name ?? "—"}</div>
        <div class="cell-scores"><Trifecta scores={toScores(idea)} /></div>
        <div class="cell-verdict"><VerdictBadge verdict={idea.source_verdict} /></div>
      </a>
    {/each}
  </div>
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
    background: var(--color-surface, #fff);
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
    background: var(--color-surface, #fff);
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
    color: var(--color-surface, #fff);
  }
  .ideas-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 12px;
    margin-bottom: 48px;
  }
  .ideas-list {
    border: 1px solid var(--color-border);
    border-radius: 8px;
    background: var(--color-surface, #fff);
    overflow: hidden;
    margin-bottom: 48px;
  }
  .list-head {
    display: grid;
    grid-template-columns: 1fr 200px 200px 100px;
    gap: 14px;
    padding: 10px 16px;
    background: var(--color-surface-elevated, #fafafa);
    border-bottom: 1px solid var(--color-border);
    font-size: 10px;
    color: var(--color-text-muted);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    font-weight: 600;
  }
  .list-row {
    display: grid;
    grid-template-columns: 1fr 200px 200px 100px;
    gap: 14px;
    padding: 14px 16px;
    align-items: center;
    border-bottom: 1px solid var(--color-border);
    transition: background 0.12s;
    color: inherit;
    text-decoration: none;
  }
  .list-row:last-child {
    border-bottom: none;
  }
  .list-row:hover {
    background: var(--color-surface-elevated, #fafafa);
  }
  .idea-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--color-text-primary);
    letter-spacing: -0.005em;
  }
  .idea-tagline {
    font-size: 12px;
    color: var(--color-text-muted);
    margin-top: 2px;
    line-height: 1.4;
    overflow: hidden;
    text-overflow: ellipsis;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
  }
  .cell-sub {
    font-size: 12px;
    color: var(--color-text-secondary, var(--color-text-primary));
  }

  @media (max-width: 900px) {
    .list-head,
    .list-row {
      grid-template-columns: 1fr;
    }
    .list-head span:not(:first-child),
    .cell-sub,
    .cell-scores,
    .cell-verdict {
      display: none;
    }
  }
</style>
