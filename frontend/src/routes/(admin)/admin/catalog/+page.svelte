<script lang="ts">
  import { goto } from "$app/navigation";
  import CurateTab from "$lib/components/catalog/CurateTab.svelte";
  import CategoriesTab from "$lib/components/catalog/CategoriesTab.svelte";
  import CollectionsTab from "$lib/components/catalog/CollectionsTab.svelte";

  let { data } = $props();

  const tab = $derived(data.tab || "curate");

  function switchTab(t: string) {
    const params = new URLSearchParams();
    params.set("tab", t);
    goto(`?${params}`, { invalidateAll: true });
  }
</script>

<svelte:head>
  <title>
    {tab === "categories"
      ? "Catalog Categories"
      : tab === "collections"
        ? "Featured Collections"
        : "Curate Catalog"} | Admin | NicheIQ
  </title>
</svelte:head>

<div class="max-w-6xl">
  <div class="mb-6">
    <h2 class="text-2xl font-bold text-text-primary">Catalog</h2>
    <p class="text-sm text-text-muted mt-1">
      Curate shared report items and manage catalog categories.
    </p>
  </div>

  <!-- Tab Bar -->
  <div class="catalog-tabs" role="tablist" aria-label="Catalog view">
    <button
      type="button"
      role="tab"
      aria-selected={tab === "curate"}
      class="catalog-tab"
      onclick={() => switchTab("curate")}
    >
      Curate Items
    </button>
    <button
      type="button"
      role="tab"
      aria-selected={tab === "categories"}
      class="catalog-tab"
      onclick={() => switchTab("categories")}
    >
      Categories
    </button>
    <button
      type="button"
      role="tab"
      aria-selected={tab === "collections"}
      class="catalog-tab"
      onclick={() => switchTab("collections")}
    >
      Collections
    </button>
  </div>

  {#if tab === "curate"}
    <CurateTab {data} categories={data.categories || []} />
  {:else if tab === "categories"}
    <CategoriesTab categories={data.categories || []} />
  {:else if tab === "collections"}
    <CollectionsTab
      collections={data.collections || []}
      categories={data.categories || []}
    />
  {/if}
</div>

<style>
  /* Tablist recipe: scoped copy of SegmentControl's compact density
     (src/lib/components/ui/SegmentControl.svelte, DESIGN_SYSTEM.md §6) —
     a plain component instance doesn't fit a goto()-driven URL tab bar. */
  .catalog-tabs {
    display: inline-flex;
    flex-wrap: wrap;
    gap: 2px;
    padding: 3px;
    margin-bottom: var(--space-6);
    border: 1px solid var(--color-border-emphasis);
    border-radius: var(--radius-md);
    background: var(--color-bg-surface);
  }

  .catalog-tab {
    border: 1px solid transparent;
    border-radius: var(--radius-sm);
    background: transparent;
    padding: 0.3rem 0.7rem;
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--color-text-secondary);
    cursor: pointer;
    transition:
      color var(--duration-fast) var(--ease-default),
      background var(--duration-fast) var(--ease-default),
      border-color var(--duration-fast) var(--ease-default);
  }

  .catalog-tab:hover {
    color: var(--color-text-primary);
  }

  .catalog-tab[aria-selected="true"] {
    border-color: var(--color-accent);
    background: var(--color-bg-elevated);
    color: var(--color-text-primary);
    box-shadow: var(--shadow-sm);
  }

  .catalog-tab:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  @media (prefers-reduced-motion: reduce) {
    .catalog-tab {
      transition: none;
    }
  }
</style>
