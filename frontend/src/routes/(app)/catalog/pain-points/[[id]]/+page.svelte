<script lang="ts">
  import { goto, pushState, replaceState } from "$app/navigation";
  import { page } from "$app/state";
  import CatalogPainPointCard from "$lib/components/catalog/CatalogPainPointCard.svelte";
  import CategoryAccordion from "$lib/components/catalog/CategoryAccordion.svelte";
  import CategorySheet from "$lib/components/catalog/CategorySheet.svelte";
  import CatalogViewToggle from "$lib/components/catalog/CatalogViewToggle.svelte";
  import PainPointListRow from "$lib/components/catalog/PainPointListRow.svelte";
  import PainPointDetailPanel from "$lib/components/catalog/PainPointDetailPanel.svelte";
  import { ChevronLeft, Filter, FolderOpen, ArrowRight } from "lucide-svelte";
  import { Breadcrumb, EmptyState } from "$lib/components/ui";
  import { resolveActiveCategory } from "$lib/utils/catalog-utils";

  let { data } = $props();

  const painPoints = $derived(data.painPointsData?.items || []);
  const totalCount = $derived(data.painPointsData?.total || painPoints.length);

  const catInfo = $derived(resolveActiveCategory(data.categories, data.filters.category));

  const breadcrumbItems = $derived.by(() => {
    const items = [
      { label: 'Dashboard', href: '/dashboard' },
      { label: 'Catalog', href: '/catalog' },
    ];
    if (catInfo.parent) {
      items.push({ label: 'Pain Points', href: '/catalog/pain-points' });
      if (catInfo.child) {
        items.push({ label: catInfo.parent.name, href: `/catalog/categories/${catInfo.parent.slug}` });
      }
    }
    return items;
  });

  const breadcrumbCurrent = $derived(
    catInfo.child?.name ?? catInfo.parent?.name ?? 'Pain Points'
  );

  // Selected item state: pushState sets page.state.selectedId; direct URL sets page.params.id
  const selectedId = $derived(page.state.selectedId ?? page.params.id ?? null);
  const selectedPainPoint = $derived(
    selectedId
      ? (painPoints.find((pp: any) => pp.id === selectedId) ?? data.selectedPainPoint ?? null)
      : null
  );

  // Mobile category sheet state
  let showCategorySheet = $state(false);

  // Desktop auto-select: first item when no selection in URL (local state, no URL update)
  let desktopAutoSelectedId = $state<string | null>(null);
  $effect(() => {
    if (painPoints.length > 0 && !selectedId) {
      desktopAutoSelectedId = painPoints[0].id;
    } else {
      desktopAutoSelectedId = null;
    }
  });

  // The effective desktop selection: URL/state takes priority, else auto-selected first
  const desktopEffectiveId = $derived(selectedId ?? desktopAutoSelectedId);
  const desktopSelectedPainPoint = $derived(
    desktopEffectiveId
      ? (painPoints.find((pp: any) => pp.id === desktopEffectiveId) ?? (selectedId ? data.selectedPainPoint : null) ?? null)
      : null
  );

  // Category name for empty state
  const activeCategoryName = $derived(catInfo.child?.name ?? catInfo.parent?.name ?? "");

  // Ref for scroll-to-top on page change
  let listPaneEl: HTMLDivElement | undefined = $state(undefined);

  // URL builders
  function ppUrl(id: string): string {
    const params = new URLSearchParams(page.url.searchParams);
    const qs = params.toString();
    return `/catalog/pain-points/${id}${qs ? `?${qs}` : ''}`;
  }

  function ppListingUrl(): string {
    const params = new URLSearchParams(page.url.searchParams);
    const qs = params.toString();
    return `/catalog/pain-points${qs ? `?${qs}` : ''}`;
  }

  // Desktop: select item (replaceState — no history entry)
  function selectItem(id: string) {
    replaceState(ppUrl(id), { selectedId: id });
  }

  function handleListKeydown(e: KeyboardEvent) {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();

    const effectiveId = desktopEffectiveId;
    const currentIndex = painPoints.findIndex((pp: any) => pp.id === effectiveId);
    let nextIndex: number;

    if (e.key === "ArrowDown") {
      nextIndex = currentIndex < painPoints.length - 1 ? currentIndex + 1 : currentIndex;
    } else {
      nextIndex = currentIndex > 0 ? currentIndex - 1 : 0;
    }

    if (nextIndex !== currentIndex && painPoints[nextIndex]) {
      replaceState(ppUrl(painPoints[nextIndex].id), { selectedId: painPoints[nextIndex].id });
      const row = listPaneEl?.querySelector(`[data-pp-id="${painPoints[nextIndex].id}"]`);
      row?.scrollIntoView({ block: "nearest" });
    }
  }

  // Mobile: pushState so Back button returns to list
  let pushedMobileDetail = $state(false);

  function openMobileDetail(id: string) {
    pushedMobileDetail = true;
    pushState(ppUrl(id), { selectedId: id });
  }

  function backToList() {
    if (pushedMobileDetail) {
      pushedMobileDetail = false;
      history.back();
    } else {
      // Direct URL arrival — goto so page.params updates (replaceState won't)
      goto(ppListingUrl(), { replaceState: true });
    }
  }

  function updateFilter(key: string, value: string) {
    const params = new URLSearchParams(page.url.searchParams);
    if (value) params.set(key, value);
    else params.delete(key);
    params.set("page", "1");
    goto(`/catalog/pain-points?${params}`, { replaceState: true, invalidateAll: true });
  }

  function paginationHref(pageNum: number): string {
    const params = new URLSearchParams(page.url.searchParams);
    params.set('page', String(pageNum));
    return `/catalog/pain-points?${params}`;
  }
</script>

<svelte:head>
  <title>Pain Points | Catalog | NicheIQ</title>
</svelte:head>

<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
  <Breadcrumb items={breadcrumbItems} current={breadcrumbCurrent} />
  <h1 class="text-2xl font-bold text-text-primary mb-4">Pain Points</h1>
  <CatalogViewToggle activeView="pain-points" category={data.filters.category} />

  <div class="flex gap-8">
    <!-- Sidebar: Category navigation -->
    <aside class="hidden lg:block w-56 flex-shrink-0 sticky top-[4.5rem] max-h-[calc(100vh-6rem)] overflow-y-auto">
      <CategoryAccordion
        categories={data.categories}
        activeCategory={data.filters.category}
        allLabel="All Pain Points"
        onSelect={(slug) => updateFilter("category", slug)}
        grouped={true}
        countField="painPoints"
      />
    </aside>

    <!-- Main -->
    <div class="flex-1 min-w-0">
      <!-- Mobile category filter trigger -->
      <div class="lg:hidden mb-4">
        <button
          class="inline-flex items-center gap-2 px-3 py-2 bg-bg-surface border border-border rounded-lg text-sm"
          onclick={() => (showCategorySheet = true)}
        >
          <Filter class="w-4 h-4" />
          {catInfo.child?.name ?? catInfo.parent?.name ?? 'All Categories'}
        </button>
      </div>

      {#if painPoints.length > 0}
        <!-- Desktop: Master-Detail Split (lg+) -->
        <div class="pp-split-layout hidden lg:flex">
          <!-- List pane -->
          <div
            class="pp-list-pane"
            bind:this={listPaneEl}
            onkeydown={handleListKeydown}
            tabindex="0"
            role="listbox"
            aria-label="Pain points list"
          >
            <!-- Toolbar row -->
            <div class="flex items-center justify-between border-b border-border pb-3 mb-1">
              <span class="mono-label">{totalCount} RESULTS</span>
              <select
                class="px-2 py-1 bg-bg-surface border border-border rounded-lg text-xs"
                value={data.filters.sort}
                onchange={(e) => updateFilter("sort", (e.target as HTMLSelectElement).value)}
              >
                <option value="newest">Newest</option>
                <option value="highest_severity">Highest Severity</option>
                <option value="highest_wtp">Highest WTP</option>
                <option value="most_mentions">Most Mentions</option>
              </select>
            </div>

            <!-- List items -->
            {#each painPoints as pp, i}
              <div data-pp-id={pp.id} role="option" aria-selected={pp.id === desktopEffectiveId}>
                <PainPointListRow
                  painPoint={pp}
                  isSelected={pp.id === desktopEffectiveId}
                  onclick={() => selectItem(pp.id)}
                  index={i}
                />
                {#if i < painPoints.length - 1}
                  <div class="gradient-divider mx-3"></div>
                {/if}
              </div>
            {/each}

            <!-- Pagination inside list pane -->
            {#if data.painPointsData && data.painPointsData.totalPages > 1}
              <div class="flex items-center justify-between mt-4 pt-3 border-t border-border px-3">
                <span class="text-xs text-text-muted">
                  Page {data.painPointsData.page} of {data.painPointsData.totalPages}
                </span>
                <div class="flex gap-2">
                  {#if data.painPointsData.page > 1}
                    <a
                      href={paginationHref(data.painPointsData.page - 1)}
                      class="text-xs px-2 py-1 rounded border border-border hover:bg-bg-elevated transition-colors text-text-secondary"
                    >
                      Prev
                    </a>
                  {/if}
                  {#if data.painPointsData.page < data.painPointsData.totalPages}
                    <a
                      href={paginationHref(data.painPointsData.page + 1)}
                      class="text-xs px-2 py-1 rounded border border-border hover:bg-bg-elevated transition-colors text-text-secondary"
                    >
                      Next
                    </a>
                  {/if}
                </div>
              </div>
            {/if}
          </div>

          <!-- Detail pane -->
          <div class="pp-detail-pane">
            {#key desktopEffectiveId}
              <PainPointDetailPanel
                painPoint={desktopSelectedPainPoint}
                {totalCount}
                categoryName={activeCategoryName}
              />
            {/key}
          </div>
        </div>

        <!-- Mobile: Card grid or detail view (< lg) -->
        <div class="lg:hidden">
          {#if selectedId && selectedPainPoint}
            <!-- Mobile detail view -->
            <button
              onclick={backToList}
              class="inline-flex items-center gap-1 text-sm text-accent hover:text-accent/80 transition-colors mb-4"
            >
              <ChevronLeft class="w-4 h-4" />
              Back to list
            </button>
            <PainPointDetailPanel
              painPoint={selectedPainPoint}
              {totalCount}
              categoryName={activeCategoryName}
            />
          {:else}
            <!-- Mobile card grid -->
            <div class="flex items-center justify-end mb-4">
              <select
                class="px-3 py-2 bg-bg-surface border border-border rounded-lg text-sm"
                value={data.filters.sort}
                onchange={(e) => updateFilter("sort", (e.target as HTMLSelectElement).value)}
              >
                <option value="newest">Newest</option>
                <option value="highest_severity">Highest Severity</option>
                <option value="highest_wtp">Highest WTP</option>
                <option value="most_mentions">Most Mentions</option>
              </select>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              {#each painPoints as pp, i}
                <CatalogPainPointCard
                  painPoint={pp}
                  index={i}
                  href="/catalog/pain-points/{pp.id}"
                  onclick={(e) => { e.preventDefault(); openMobileDetail(pp.id); }}
                />
              {/each}
            </div>

            <!-- Mobile pagination -->
            {#if data.painPointsData && data.painPointsData.totalPages > 1}
              <div class="flex items-center justify-between mt-6">
                <span class="text-sm text-text-muted">
                  Page {data.painPointsData.page} of {data.painPointsData.totalPages}
                </span>
                <div class="flex gap-2">
                  {#if data.painPointsData.page > 1}
                    <a
                      href={paginationHref(data.painPointsData.page - 1)}
                      class="text-sm px-3 py-1 rounded border border-border hover:bg-bg-elevated transition-colors text-text-secondary"
                    >
                      Previous
                    </a>
                  {/if}
                  {#if data.painPointsData.page < data.painPointsData.totalPages}
                    <a
                      href={paginationHref(data.painPointsData.page + 1)}
                      class="text-sm px-3 py-1 rounded border border-border hover:bg-bg-elevated transition-colors text-text-secondary"
                    >
                      Next
                    </a>
                  {/if}
                </div>
              </div>
            {/if}
          {/if}
        </div>
      {:else}
        <EmptyState icon={FolderOpen} title="No pain points found" variant="muted" size="md">
          {#if data.filters.category}
            <a href="/catalog/categories/{data.filters.category}"
               class="inline-flex items-center gap-1 text-sm text-accent hover:text-accent/80 transition-colors">
              View this category <ArrowRight class="w-3.5 h-3.5" />
            </a>
            <a href="/catalog/pain-points"
               class="inline-flex items-center gap-1 text-sm text-text-secondary hover:text-text-primary transition-colors">
              Browse all pain points <ArrowRight class="w-3.5 h-3.5" />
            </a>
          {:else}
            <a href="/catalog" class="inline-flex items-center gap-1 text-sm text-accent hover:text-accent/80 transition-colors">
              Browse the catalog <ArrowRight class="w-3.5 h-3.5" />
            </a>
          {/if}
        </EmptyState>
      {/if}
    </div>
  </div>
</div>

<CategorySheet
  open={showCategorySheet}
  categories={data.categories}
  activeCategory={data.filters.category}
  allLabel="All Pain Points"
  onSelect={(slug) => updateFilter("category", slug)}
  onClose={() => (showCategorySheet = false)}
  grouped={true}
  countField="painPoints"
/>

<style>
  .pp-split-layout {
    display: flex;
    gap: 1rem;
    align-items: flex-start;
  }

  .pp-list-pane {
    width: 340px;
    flex-shrink: 0;
    overflow-y: auto;
    max-height: calc(100vh - 5rem);
  }

  .pp-list-pane:focus-visible {
    outline: none;
  }

  .pp-detail-pane {
    flex: 1;
    min-width: 0;
    position: sticky;
    top: 4.5rem;
    max-height: calc(100vh - 5rem);
    overflow-y: auto;
    border-radius: var(--radius-xl);
    border: 1px solid var(--color-border);
    background: var(--color-bg-elevated);
  }
</style>
