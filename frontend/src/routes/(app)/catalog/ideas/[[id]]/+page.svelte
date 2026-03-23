<script lang="ts">
  import { goto, pushState, replaceState } from "$app/navigation";
  import { page } from "$app/state";
  import CatalogIdeaCard from "$lib/components/catalog/CatalogIdeaCard.svelte";
  import CategoryAccordion from "$lib/components/catalog/CategoryAccordion.svelte";
  import CategorySheet from "$lib/components/catalog/CategorySheet.svelte";
  import CatalogViewToggle from "$lib/components/catalog/CatalogViewToggle.svelte";
  import SolutionDetail from "$lib/components/SolutionDetail.svelte";
  import { Filter, FolderOpen, ArrowRight } from "lucide-svelte";
  import { PageHeader, EmptyState } from "$lib/components/ui";
  import { resolveActiveCategory } from "$lib/utils/catalog-utils";

  let { data } = $props();

  const ideas = $derived(data.ideasData?.items || []);

  const catInfo = $derived(resolveActiveCategory(data.categories, data.filters.category));

  const breadcrumbItems = $derived.by(() => {
    const items = [
      { label: 'Dashboard', href: '/dashboard' },
      { label: 'Catalog', href: '/catalog' },
    ];
    if (catInfo.parent) {
      items.push({ label: 'Ideas', href: '/catalog/ideas' });
      if (catInfo.child) {
        items.push({ label: catInfo.parent.name, href: `/catalog/categories/${catInfo.parent.slug}` });
      }
    }
    return items;
  });

  const breadcrumbCurrent = $derived(
    catInfo.child?.name ?? catInfo.parent?.name ?? 'Ideas'
  );

  // Modal state: pushState sets page.state.openId; direct URL sets page.params.id
  const openId = $derived(page.state.openId ?? page.params.id ?? null);
  const openIdea = $derived(
    openId
      ? (ideas.find((i: any) => i.id === openId) ?? data.openIdea ?? null)
      : null
  );
  const openIndex = $derived(openIdea ? ideas.findIndex((i: any) => i.id === openId) : -1);
  const isModalOpen = $derived(!!openIdea);

  // When item isn't in current page list, pass single-element array to disable nav
  const modalSolutions = $derived(openIndex >= 0 ? ideas : (openIdea ? [openIdea] : []));
  const modalIndex = $derived(openIndex >= 0 ? openIndex : 0);

  // URL builders
  function ideaUrl(id: string): string {
    const params = new URLSearchParams(page.url.searchParams);
    const qs = params.toString();
    return `/catalog/ideas/${id}${qs ? `?${qs}` : ''}`;
  }

  function listingUrl(): string {
    const params = new URLSearchParams(page.url.searchParams);
    const qs = params.toString();
    return `/catalog/ideas${qs ? `?${qs}` : ''}`;
  }

  // Mobile category sheet state
  let showCategorySheet = $state(false);

  // Track whether modal was opened via pushState (vs direct URL)
  let pushedModal = $state(false);

  function openIdeaModal(id: string) {
    showCategorySheet = false; // ensure sheet is closed before modal
    if (isModalOpen) {
      replaceState(ideaUrl(id), { openId: id });
    } else {
      pushedModal = true;
      pushState(ideaUrl(id), { openId: id });
    }
  }

  function closeModal() {
    if (pushedModal) {
      pushedModal = false;
      history.back();
    } else {
      // Direct URL arrival — goto so page.params updates (replaceState won't)
      goto(listingUrl(), { replaceState: true });
    }
  }

  function handleNavigate(index: number) {
    if (modalSolutions[index]) {
      replaceState(ideaUrl(modalSolutions[index].id), { openId: modalSolutions[index].id });
    }
  }

  function updateFilter(key: string, value: string) {
    const params = new URLSearchParams(page.url.searchParams);
    if (value) params.set(key, value);
    else params.delete(key);
    params.set("page", "1");
    goto(`/catalog/ideas?${params}`, { replaceState: true, invalidateAll: true });
  }

  function paginationHref(pageNum: number): string {
    const params = new URLSearchParams(page.url.searchParams);
    params.set('page', String(pageNum));
    return `/catalog/ideas?${params}`;
  }
</script>

<svelte:head>
  <title>Ideas | Catalog | NicheIQ</title>
</svelte:head>

<div>
  <PageHeader
    breadcrumbItems={breadcrumbItems}
    breadcrumbCurrent={breadcrumbCurrent}
    title="Solution Ideas"
  >
    {#snippet below()}
      <CatalogViewToggle activeView="ideas" category={data.filters.category} />
    {/snippet}
  </PageHeader>

  <div class="flex gap-8">
    <!-- Sidebar: Category navigation -->
    <aside class="hidden lg:block w-56 flex-shrink-0 sticky top-[4.5rem] max-h-[calc(100vh-6rem)] overflow-y-auto">
      <CategoryAccordion
        categories={data.categories}
        activeCategory={data.filters.category}
        allLabel="All Ideas"
        onSelect={(slug) => updateFilter("category", slug)}
        grouped={true}
        countField="ideas"
      />
    </aside>

    <!-- Main content -->
    <div class="flex-1 min-w-0">
      <!-- Sort + mobile category filter -->
      <div class="flex items-center justify-between mb-4">
        <button
          class="lg:hidden inline-flex items-center gap-2 px-3 py-2 bg-bg-surface border border-border rounded-lg text-sm"
          onclick={() => (showCategorySheet = true)}
        >
          <Filter class="w-4 h-4" />
          {catInfo.child?.name ?? catInfo.parent?.name ?? 'All Categories'}
        </button>

        <select
          class="px-3 py-2 bg-bg-surface border border-border rounded-lg text-sm"
          value={data.filters.sort}
          onchange={(e) => updateFilter("sort", (e.target as HTMLSelectElement).value)}
        >
          <option value="newest">Newest</option>
          <option value="highest_market_fit">Highest Market Fit</option>
          <option value="highest_novelty">Most Novel</option>
        </select>
      </div>

      <!-- Ideas grid -->
      {#if ideas.length > 0}
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          {#each ideas as idea, i}
            <CatalogIdeaCard
              {idea}
              index={i}
              href="/catalog/ideas/{idea.id}"
              onclick={(e) => { e.preventDefault(); openIdeaModal(idea.id); }}
            />
          {/each}
        </div>
      {:else}
        <EmptyState icon={FolderOpen} title="No ideas found" variant="muted" size="md">
          {#if data.filters.category}
            <a href="/catalog/categories/{data.filters.category}"
               class="inline-flex items-center gap-1 text-sm text-accent hover:text-accent/80 transition-colors">
              View this category <ArrowRight class="w-3.5 h-3.5" />
            </a>
            <a href="/catalog/ideas"
               class="inline-flex items-center gap-1 text-sm text-text-secondary hover:text-text-primary transition-colors">
              Browse all ideas <ArrowRight class="w-3.5 h-3.5" />
            </a>
          {:else}
            <a href="/catalog" class="inline-flex items-center gap-1 text-sm text-accent hover:text-accent/80 transition-colors">
              Browse the catalog <ArrowRight class="w-3.5 h-3.5" />
            </a>
          {/if}
        </EmptyState>
      {/if}

      <!-- Pagination -->
      {#if data.ideasData && data.ideasData.totalPages > 1}
        <div class="flex items-center justify-between mt-6">
          <span class="text-sm text-text-muted">
            Page {data.ideasData.page} of {data.ideasData.totalPages}
          </span>
          <div class="flex gap-2">
            {#if data.ideasData.page > 1}
              <a
                href={paginationHref(data.ideasData.page - 1)}
                class="text-sm px-3 py-1 rounded border border-border hover:bg-bg-elevated transition-colors text-text-secondary"
              >
                Previous
              </a>
            {/if}
            {#if data.ideasData.page < data.ideasData.totalPages}
              <a
                href={paginationHref(data.ideasData.page + 1)}
                class="text-sm px-3 py-1 rounded border border-border hover:bg-bg-elevated transition-colors text-text-secondary"
              >
                Next
              </a>
            {/if}
          </div>
        </div>
      {/if}
    </div>
  </div>
</div>

<CategorySheet
  open={showCategorySheet}
  categories={data.categories}
  activeCategory={data.filters.category}
  allLabel="All Ideas"
  onSelect={(slug) => updateFilter("category", slug)}
  onClose={() => (showCategorySheet = false)}
  grouped={true}
  countField="ideas"
/>

{#if isModalOpen && openIdea}
  <SolutionDetail
    open={true}
    solution={openIdea}
    solutions={modalSolutions}
    currentIndex={modalIndex}
    onNavigate={handleNavigate}
    onClose={closeModal}
  />
{/if}
