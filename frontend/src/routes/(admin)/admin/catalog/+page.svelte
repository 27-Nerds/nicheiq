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
  <div class="flex rounded-lg border border-border overflow-hidden mb-6">
    <button
      class="px-5 py-2.5 text-sm font-medium transition-colors {tab === 'curate'
        ? 'bg-accent text-white'
        : 'bg-bg-surface text-text-secondary hover:bg-bg-elevated'}"
      onclick={() => switchTab("curate")}
    >
      Curate Items
    </button>
    <button
      class="px-5 py-2.5 text-sm font-medium transition-colors {tab === 'categories'
        ? 'bg-accent text-white'
        : 'bg-bg-surface text-text-secondary hover:bg-bg-elevated'}"
      onclick={() => switchTab("categories")}
    >
      Categories
    </button>
    <button
      class="px-5 py-2.5 text-sm font-medium transition-colors {tab === 'collections'
        ? 'bg-accent text-white'
        : 'bg-bg-surface text-text-secondary hover:bg-bg-elevated'}"
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
