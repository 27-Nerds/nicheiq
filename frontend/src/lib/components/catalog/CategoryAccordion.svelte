<script lang="ts">
  import { untrack } from "svelte";
  import { SvelteSet } from "svelte/reactivity";
  import { slide } from "svelte/transition";
  import { ChevronRight, Search, X } from "lucide-svelte";
  import { groupCategories, computeCategoryTotalItems, type CategoryGroup as CatalogCategoryGroup } from "$lib/utils/catalog-utils";

  export interface CategoryItem {
    name: string;
    slug: string;
    _count?: { ideas: number; painPoints: number };
  }

  export interface CategoryGroup extends CategoryItem {
    children?: CategoryItem[];
    superGroup?: { id: string; name: string; slug: string; sortOrder: number } | null;
    _hasSearchMatch?: boolean;
    _hasActiveChild?: boolean;
  }

  interface Props {
    categories: CategoryGroup[];
    activeCategory: string;
    allLabel: string;
    onSelect: (slug: string) => void;
    /** Add extra vertical padding for touch targets (mobile sheet) */
    touchFriendly?: boolean;
    /** Enable super-group tier (three-level accordion) */
    grouped?: boolean;
    /** When set, count only this field instead of summing ideas + painPoints */
    countField?: 'ideas' | 'painPoints';
  }

  let {
    categories,
    activeCategory,
    allLabel,
    onSelect,
    touchFriendly = false,
    grouped = false,
    countField,
  }: Props = $props();

  /** Compute count for a single child category, respecting countField */
  function childCount(child: CategoryItem): number {
    return countField ? (child._count?.[countField] ?? 0) : (child._count?.ideas ?? 0) + (child._count?.painPoints ?? 0);
  }

  let searchQuery = $state("");
  let expandedSlugs = new SvelteSet<string>();
  let expandedGroups = new SvelteSet<string>();

  const isSearchActive = $derived(searchQuery.trim() !== "");

  const showSearch = $derived(() => {
    let total = categories.length;
    for (const cat of categories) {
      total += cat.children?.length ?? 0;
    }
    return total >= 8;
  });

  // Annotate categories with search/active flags
  function annotateCategories(cats: CategoryGroup[], q: string): CategoryGroup[] {
    if (!q) {
      return cats.map((parent) => ({
        ...parent,
        _hasSearchMatch: false,
        _hasActiveChild:
          parent.slug === activeCategory ||
          parent.children?.some((c) => c.slug === activeCategory) || false,
      }));
    }

    const results: CategoryGroup[] = [];
    for (const parent of cats) {
      const parentMatches = parent.name.toLowerCase().includes(q);
      const matchingChildren = (parent.children ?? []).filter((c) =>
        c.name.toLowerCase().includes(q)
      );

      if (parentMatches) {
        results.push({
          ...parent,
          _hasSearchMatch: true,
          _hasActiveChild:
            parent.slug === activeCategory ||
            parent.children?.some((c) => c.slug === activeCategory) || false,
        });
      } else if (matchingChildren.length > 0) {
        results.push({
          ...parent,
          children: matchingChildren,
          _hasSearchMatch: true,
          _hasActiveChild:
            parent.slug === activeCategory ||
            matchingChildren.some((c) => c.slug === activeCategory),
        });
      }
    }
    return results;
  }

  // Flat mode: filtered categories
  const filteredCategories = $derived.by(() => {
    const q = searchQuery.trim().toLowerCase();
    return annotateCategories(categories, q);
  });

  // Grouped mode: super-groups with filtered categories
  const filteredGroups = $derived.by((): { name: string; categories: CategoryGroup[]; _hasMatch: boolean }[] => {
    if (!grouped) return [];
    const q = searchQuery.trim().toLowerCase();
    const superGroups = groupCategories(categories);
    return superGroups.map((sg) => {
      const annotated = annotateCategories(sg.categories as CategoryGroup[], q);
      const filtered = q ? annotated.filter((c) => c._hasSearchMatch) : annotated;
      return {
        name: sg.name,
        categories: filtered,
        _hasMatch: filtered.length > 0,
      };
    }).filter((sg) => sg.categories.length > 0);
  });

  // Auto-expand the parent (and super-group) that contains the active category
  $effect(() => {
    const slug = activeCategory;
    if (!slug) return;

    const parentCat = categories.find(
      (p) => p.slug === slug || p.children?.some((c) => c.slug === slug)
    );
    if (parentCat) {
      untrack(() => expandedSlugs.add(parentCat.slug));
    }

    // Also expand the super-group containing this parent
    if (grouped && parentCat) {
      const groups = groupCategories(categories);
      for (const sg of groups) {
        if (sg.categories.some((c) => c.slug === parentCat.slug)) {
          untrack(() => expandedGroups.add(sg.name));
          break;
        }
      }
    }
  });

  // Clear search when active category changes
  $effect(() => {
    activeCategory;
    untrack(() => {
      searchQuery = "";
    });
  });

  function toggleParent(slug: string) {
    if (isSearchActive) return;
    if (expandedSlugs.has(slug)) expandedSlugs.delete(slug);
    else expandedSlugs.add(slug);
  }

  function toggleGroup(name: string) {
    if (isSearchActive) return;
    if (expandedGroups.has(name)) expandedGroups.delete(name);
    else expandedGroups.add(name);
  }

  const itemPy = $derived(touchFriendly ? "py-2.5" : "py-1.5");
  const parentPy = $derived(touchFriendly ? "py-3" : "py-2");
</script>

{#if showSearch()}
  <div class="sticky top-0 z-10 bg-bg-surface pb-2">
    <div class="relative">
      <Search
        class="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted pointer-events-none"
      />
      <input
        type="text"
        bind:value={searchQuery}
        placeholder="Filter categories..."
        autocomplete="off"
        spellcheck={false}
        class="w-full pl-8 pr-8 {touchFriendly
          ? 'py-2.5'
          : 'py-1.5'} text-sm rounded-lg border border-border bg-bg-surface text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent"
      />
      {#if searchQuery}
        <button
          class="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 text-text-muted hover:text-text-primary transition-colors"
          onclick={() => (searchQuery = "")}
          aria-label="Clear search"
        >
          <X class="w-3.5 h-3.5" />
        </button>
      {/if}
    </div>
  </div>
{/if}

<nav class="space-y-0.5" aria-label="Category navigation">
  <!-- "All" top-level item -->
  <button
    class="block w-full text-left px-3 {parentPy} rounded-lg text-sm transition-colors
      {!activeCategory
      ? 'bg-accent/10 text-accent font-medium'
      : 'text-text-secondary hover:bg-bg-elevated'}"
    onclick={() => onSelect("")}
  >
    {allLabel}
  </button>

  {#if grouped}
    <!-- ===== GROUPED MODE: Super-group → Parent → Child ===== -->
    {#each filteredGroups as sg (sg.name)}
      {@const isGroupExpanded = isSearchActive || expandedGroups.has(sg.name)}
      {@const hasActiveInGroup = sg.categories.some((c) => c._hasActiveChild)}

      <div class="mt-1">
        <!-- Super-group header -->
        <button
          class="flex w-full items-center gap-1.5 px-2 {parentPy} rounded-lg text-xs font-semibold uppercase tracking-wider transition-colors
            {hasActiveInGroup
            ? 'text-text-primary'
            : 'text-text-muted hover:bg-bg-elevated hover:text-text-secondary'}"
          onclick={() => toggleGroup(sg.name)}
          aria-expanded={isGroupExpanded}
        >
          <ChevronRight
            class="w-3 h-3 flex-shrink-0 transition-transform duration-200
              {isGroupExpanded ? 'rotate-90' : ''}"
          />
          <span>{sg.name}</span>
        </button>

        {#if isGroupExpanded}
          <div transition:slide={{ duration: isSearchActive ? 0 : 200 }}>
            <!-- Parent categories within super-group -->
            {#each sg.categories as parent (parent.slug)}
              {@const isExpanded =
                parent._hasSearchMatch || expandedSlugs.has(parent.slug)}
              {@const hasActiveChild = parent._hasActiveChild}
              {@const parentTotal = computeCategoryTotalItems(parent as CatalogCategoryGroup, countField)}

              <div class="ml-2 {hasActiveChild ? 'border-l-2 border-accent rounded-l-sm' : ''}">
                <button
                  class="flex w-full items-center gap-2 px-3 {parentPy} rounded-lg text-sm transition-colors
                    {hasActiveChild
                    ? 'text-text-primary font-medium'
                    : 'text-text-secondary hover:bg-bg-elevated'}"
                  onclick={() => toggleParent(parent.slug)}
                  aria-expanded={isExpanded}
                >
                  <ChevronRight
                    class="w-3.5 h-3.5 flex-shrink-0 transition-transform duration-200
                      {isExpanded ? 'rotate-90' : ''}"
                  />
                  <span class="truncate">{parent.name}</span>
                  {#if parentTotal > 0}
                    <span class="shrink-0 text-xs text-text-muted font-mono tabular-nums ml-auto">{parentTotal}</span>
                  {/if}
                </button>

                {#if isExpanded}
                  <div transition:slide={{ duration: isSearchActive ? 0 : 200 }}>
                    <div class="space-y-0.5 pb-1">
                      {#if !isSearchActive}
                        <button
                          class="block w-full text-left pl-9 pr-3 {itemPy} rounded-lg text-sm transition-colors
                            {activeCategory === parent.slug
                            ? 'bg-accent/10 text-accent font-medium'
                            : 'text-text-muted hover:bg-bg-elevated'}"
                          onclick={() => onSelect(parent.slug)}
                        >
                          All in {parent.name}
                        </button>
                      {/if}

                      {#each parent.children || [] as child (child.slug)}
                        {@const childTotal = childCount(child)}
                        <button
                          class="flex w-full items-center gap-2 text-left pl-9 pr-3 {itemPy} rounded-lg text-sm transition-colors
                            {activeCategory === child.slug
                            ? 'bg-accent/10 text-accent font-medium'
                            : 'text-text-secondary hover:bg-bg-elevated'}
                            {childTotal === 0 && activeCategory !== child.slug ? 'opacity-50' : ''}"
                          onclick={() => onSelect(child.slug)}
                        >
                          <span class="truncate">{child.name}</span>
                          {#if childTotal > 0}
                            <span class="shrink-0 text-xs text-text-muted font-mono tabular-nums ml-auto">{childTotal}</span>
                          {/if}
                        </button>
                      {/each}
                    </div>
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {/each}
  {:else}
    <!-- ===== FLAT MODE: Parent → Child (original behavior) ===== -->
    {#each filteredCategories as parent (parent.slug)}
      {@const isExpanded =
        parent._hasSearchMatch || expandedSlugs.has(parent.slug)}
      {@const hasActiveChild = parent._hasActiveChild}
      {@const parentTotal = computeCategoryTotalItems(parent as CatalogCategoryGroup, countField)}

      <div class={hasActiveChild ? "border-l-2 border-accent rounded-l-sm" : ""}>
        <button
          class="flex w-full items-center gap-2 px-3 {parentPy} rounded-lg text-sm transition-colors
            {hasActiveChild
            ? 'text-text-primary font-medium'
            : 'text-text-secondary hover:bg-bg-elevated'}"
          onclick={() => toggleParent(parent.slug)}
          aria-expanded={isExpanded}
        >
          <ChevronRight
            class="w-3.5 h-3.5 flex-shrink-0 transition-transform duration-200
              {isExpanded ? 'rotate-90' : ''}"
          />
          <span class="truncate">{parent.name}</span>
          {#if parentTotal > 0}
            <span class="shrink-0 text-xs text-text-muted font-mono tabular-nums ml-auto">{parentTotal}</span>
          {/if}
        </button>

        {#if isExpanded}
          <div transition:slide={{ duration: isSearchActive ? 0 : 200 }}>
            <div class="space-y-0.5 pb-1">
              {#if !isSearchActive}
                <button
                  class="block w-full text-left pl-7 pr-3 {itemPy} rounded-lg text-sm transition-colors
                    {activeCategory === parent.slug
                    ? 'bg-accent/10 text-accent font-medium'
                    : 'text-text-muted hover:bg-bg-elevated'}"
                  onclick={() => onSelect(parent.slug)}
                >
                  All in {parent.name}
                </button>
              {/if}

              {#each parent.children || [] as child (child.slug)}
                {@const childTotal = childCount(child)}
                <button
                  class="flex w-full items-center gap-2 text-left pl-7 pr-3 {itemPy} rounded-lg text-sm transition-colors
                    {activeCategory === child.slug
                    ? 'bg-accent/10 text-accent font-medium'
                    : 'text-text-secondary hover:bg-bg-elevated'}
                    {childTotal === 0 && activeCategory !== child.slug ? 'opacity-50' : ''}"
                  onclick={() => onSelect(child.slug)}
                >
                  <span class="truncate">{child.name}</span>
                  {#if childTotal > 0}
                    <span class="shrink-0 text-xs text-text-muted font-mono tabular-nums ml-auto">{childTotal}</span>
                  {/if}
                </button>
              {/each}
            </div>
          </div>
        {/if}
      </div>
    {/each}
  {/if}

  <!-- Empty state when search yields no results -->
  {#if isSearchActive && (grouped ? filteredGroups.length === 0 : filteredCategories.length === 0)}
    <p class="px-3 py-4 text-sm text-text-muted text-center">
      No categories match.
    </p>
  {/if}
</nav>
