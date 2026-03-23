<script lang="ts">
  import { FolderOpen, ArrowRight } from "lucide-svelte";
  import CatalogIdeaCard from "$lib/components/catalog/CatalogIdeaCard.svelte";
  import CatalogPainPointCard from "$lib/components/catalog/CatalogPainPointCard.svelte";
  import CatalogSearch from "$lib/components/catalog/CatalogSearch.svelte";
  import SubcategoryGrid from "$lib/components/catalog/SubcategoryGrid.svelte";
  import { PageHeader } from "$lib/components/ui";
  import { groupCategories } from "$lib/utils/catalog-utils";

  let { data } = $props();

  const stats = $derived(data.stats);
  const newestIdeas = $derived(data.newestIdeas);
  const newestPainPoints = $derived(data.newestPainPoints);
  const parentCategories = $derived(data.categories.filter((c: any) => !c.parentId));

  // Group L1 categories by SuperGroup
  const superGroups = $derived(groupCategories(parentCategories));

  /** Check if all L2 children of an L1 have 0 items */
  function isL1Empty(cat: any): boolean {
    return (cat.totalItems ?? 0) === 0;
  }
</script>

<svelte:head>
  <title>Catalog | NicheIQ</title>
</svelte:head>

<div>
  <PageHeader
    breadcrumbItems={[{ label: 'Dashboard', href: '/dashboard' }]}
    breadcrumbCurrent="Catalog"
    title="Catalog"
    subtitle="Browse curated SaaS ideas and validated market pain points across {superGroups.length} sectors and {parentCategories.length} industries."
  >
    {#snippet below()}
      <div class="max-w-2xl">
        <CatalogSearch />
      </div>
    {/snippet}
  </PageHeader>

  <!-- Browse by Industry — 3-tier: SuperGroup → L1 → L2 -->
  {#if parentCategories.length > 0}
    <div class="mb-10">
      <h2 class="text-lg font-semibold text-text-primary mb-6">Industries</h2>

      <!-- SuperGroup sections -->
      {#each superGroups as sg (sg.name)}
        <div class="mb-8">
          <!-- SuperGroup header — quiet divider -->
          <h3 class="text-xs uppercase tracking-widest font-semibold text-text-muted mb-4 pb-2 border-b border-border">
            {sg.name}
          </h3>

          <!-- L1 categories within this SuperGroup -->
          {#each sg.categories as l1 (l1.slug)}
            {@const empty = isL1Empty(l1)}
            <div class="mb-10 {empty ? 'opacity-50' : ''}">
              <!-- L1 sub-header — primary scannable unit -->
              <div class="flex items-baseline gap-2 mb-3">
                <a
                  href="/catalog/categories/{l1.slug}"
                  class="text-base font-semibold transition-colors {empty ? 'text-text-muted' : 'text-text-primary hover:text-accent'}"
                >
                  {l1.name}
                </a>
                <span class="text-xs text-text-muted">
                  {l1.totalItems ?? 0} {(l1.totalItems ?? 0) === 1 ? 'item' : 'items'}
                </span>
              </div>

              <SubcategoryGrid
                children={l1.children || []}
                emptyMode="link"
                emptyLinkHref="/catalog/categories/{l1.slug}"
              />
            </div>
          {/each}
        </div>
      {/each}
    </div>
  {/if}

  <!-- Newest Ideas -->
  {#if newestIdeas.length > 0}
    <div class="mb-10">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-semibold text-text-primary">Newest Ideas</h2>
        <a
          href="/catalog/ideas"
          class="inline-flex items-center gap-1 text-sm text-accent hover:text-accent/80 transition-colors"
        >
          View all{#if stats} ({stats.ideas}){/if} <ArrowRight class="w-4 h-4" />
        </a>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {#each newestIdeas as idea, i}
          <CatalogIdeaCard {idea} index={i} href="/catalog/ideas/{idea.id}" />
        {/each}
      </div>
    </div>
  {/if}

  <!-- Newest Pain Points -->
  {#if newestPainPoints.length > 0}
    <div class="mb-10">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-semibold text-text-primary">Newest Pain Points</h2>
        <a
          href="/catalog/pain-points"
          class="inline-flex items-center gap-1 text-sm text-accent hover:text-accent/80 transition-colors"
        >
          View all{#if stats} ({stats.painPoints}){/if} <ArrowRight class="w-4 h-4" />
        </a>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {#each newestPainPoints as pp, i}
          <CatalogPainPointCard painPoint={pp} index={i} href="/catalog/pain-points/{pp.id}" />
        {/each}
      </div>
    </div>
  {/if}

  {#if !stats || (stats.ideas === 0 && stats.painPoints === 0 && newestIdeas.length === 0 && newestPainPoints.length === 0 && parentCategories.length === 0)}
    <div class="mt-8 bg-bg-surface border border-border rounded-xl p-8 text-center">
      <FolderOpen class="w-8 h-8 mx-auto mb-2 text-text-muted opacity-50" />
      <p class="text-text-muted">The catalog is empty. Check back soon for curated research insights.</p>
    </div>
  {/if}
</div>
