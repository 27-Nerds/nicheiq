<script lang="ts">
  import { FolderOpen, ArrowRight, Search, X } from "lucide-svelte";
  import CatalogIdeaCard from "$lib/components/catalog/CatalogIdeaCard.svelte";
  import CatalogPainPointCard from "$lib/components/catalog/CatalogPainPointCard.svelte";
  import SubcategoryGrid from "$lib/components/catalog/SubcategoryGrid.svelte";
  import { Breadcrumb, EmptyState } from "$lib/components/ui";
  import { buildLeafCategoryListingUrl } from "$lib/utils/catalog-utils";

  let { data } = $props();

  const category = $derived(data.category);
  const children = $derived(data.children);
  const parentCat = $derived(data.parent);
  const previewIdeas = $derived(data.previewIdeas);
  const previewPainPoints = $derived(data.previewPainPoints);
  const totalIdeas = $derived(data.totalIdeas);
  const totalPainPoints = $derived(data.totalPainPoints);
  const isEmpty = $derived(previewIdeas.length === 0 && previewPainPoints.length === 0);

  // Subcategory filter
  const FILTER_THRESHOLD = 8;
  let subcatFilter = $state("");
  const showSubcatFilter = $derived(children.length > FILTER_THRESHOLD);
  const isFiltering = $derived(subcatFilter.trim() !== "");

  const filteredChildren = $derived.by(() => {
    const q = subcatFilter.trim().toLowerCase();
    if (!q) return children;
    return children.filter((c: any) => c.name.toLowerCase().includes(q));
  });

</script>

<svelte:head>
  <title>{category.name} | Catalog | NicheIQ</title>
</svelte:head>

<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
  <Breadcrumb
    items={[
      { label: 'Dashboard', href: '/dashboard' },
      { label: 'Catalog', href: '/catalog' },
      ...(parentCat ? [{ label: parentCat.name, href: `/catalog/categories/${parentCat.slug}` }] : []),
    ]}
    current={category.name}
  />

  <!-- Category header -->
  <div class="mb-8">
    <h1 class="text-2xl font-bold text-text-primary">{category.name}</h1>
    {#if category.description}
      <p class="text-text-secondary mt-2">{category.description}</p>
    {/if}
    <div class="flex items-center gap-4 mt-3 text-sm">
      {#if children.length > 0}
        <span class="text-text-muted">{children.length} {children.length === 1 ? 'subcategory' : 'subcategories'}</span>
      {/if}
      {#if totalIdeas > 0}
        <a
          href="/catalog/ideas?category={category.slug}"
          class="inline-flex items-center gap-1 text-accent hover:text-accent/80 transition-colors"
        >
          {totalIdeas} {totalIdeas === 1 ? 'idea' : 'ideas'} <ArrowRight class="w-3.5 h-3.5" />
        </a>
      {/if}
      {#if totalPainPoints > 0}
        <a
          href="/catalog/pain-points?category={category.slug}"
          class="inline-flex items-center gap-1 text-accent hover:text-accent/80 transition-colors"
        >
          {totalPainPoints} {totalPainPoints === 1 ? 'pain point' : 'pain points'} <ArrowRight class="w-3.5 h-3.5" />
        </a>
      {/if}
    </div>
  </div>

  <!-- Preview Ideas (above subcategories for immediate value) -->
  {#if previewIdeas.length > 0}
    <div class="mb-10">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-semibold text-text-primary">Ideas</h2>
        {#if totalIdeas > 3}
          <a
            href="/catalog/ideas?category={category.slug}"
            class="inline-flex items-center gap-1 text-sm text-accent hover:text-accent/80 transition-colors"
          >
            View all {totalIdeas} <ArrowRight class="w-4 h-4" />
          </a>
        {/if}
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {#each previewIdeas as idea, i}
          <CatalogIdeaCard {idea} index={i} href="/catalog/ideas/{idea.id}" />
        {/each}
      </div>
    </div>
  {/if}

  <!-- Preview Pain Points -->
  {#if previewPainPoints.length > 0}
    <div class="mb-10">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-semibold text-text-primary">Pain Points</h2>
        {#if totalPainPoints > 3}
          <a
            href="/catalog/pain-points?category={category.slug}"
            class="inline-flex items-center gap-1 text-sm text-accent hover:text-accent/80 transition-colors"
          >
            View all {totalPainPoints} <ArrowRight class="w-4 h-4" />
          </a>
        {/if}
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {#each previewPainPoints as pp, i}
          <CatalogPainPointCard painPoint={pp} index={i} href="/catalog/pain-points/{pp.id}" />
        {/each}
      </div>
    </div>
  {/if}

  <!-- Subcategories -->
  {#if children.length > 0}
    <div class="mb-10">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-semibold text-text-primary">Subcategories</h2>
        {#if isFiltering}
          <span class="text-xs text-text-muted">{filteredChildren.length} of {children.length}</span>
        {/if}
      </div>

      <!-- Filter -->
      {#if showSubcatFilter}
        <div class="relative max-w-xs mb-4">
          <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted pointer-events-none" />
          <input
            type="text"
            bind:value={subcatFilter}
            placeholder="Filter subcategories..."
            autocomplete="off"
            spellcheck={false}
            class="w-full pl-9 pr-8 py-2 text-sm rounded-lg border border-border bg-bg-surface text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent"
          />
          {#if subcatFilter}
            <button
              class="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 text-text-muted hover:text-text-primary transition-colors"
              onclick={() => (subcatFilter = "")}
              aria-label="Clear filter"
            >
              <X class="w-3.5 h-3.5" />
            </button>
          {/if}
        </div>
      {/if}

      {#if filteredChildren.length > 0}
        <SubcategoryGrid
          children={filteredChildren}
          emptyMode="toggle"
          cardHref={(child) => buildLeafCategoryListingUrl(child.slug, child._count?.ideas ?? 0, child._count?.painPoints ?? 0)}
          showAll={isFiltering}
        />
      {:else if subcatFilter}
        <div class="bg-bg-surface border border-border rounded-xl p-6 text-center">
          <p class="text-sm text-text-muted">No subcategories match "{subcatFilter.trim()}"</p>
        </div>
      {/if}
    </div>
  {/if}

  <!-- Empty state -->
  {#if isEmpty && children.length === 0}
    <EmptyState icon={FolderOpen} title="No items in this category yet" variant="muted" size="md">
      <a
        href="/catalog"
        class="inline-flex items-center gap-1 text-sm text-accent hover:text-accent/80 transition-colors"
      >
        Browse other categories <ArrowRight class="w-3.5 h-3.5" />
      </a>
    </EmptyState>
  {/if}
</div>
