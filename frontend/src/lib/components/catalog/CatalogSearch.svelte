<script lang="ts">
  import { goto } from "$app/navigation";
  import { Search, X, Folder, Lightbulb, AlertCircle, Loader2 } from "lucide-svelte";
  import { buildLeafCategoryListingUrl } from "$lib/utils/catalog-utils";

  interface SearchResults {
    categories: { id: string; name: string; slug: string; isParent: boolean; ideaCount: number; painPointCount: number; childCount: number }[];
    ideas: { id: string; solution_name: string; description: string; market_fit_score: number | null; category: { name: string; slug: string } | null }[];
    painPoints: { id: string; title: string; description: string; severity_score: number | null; category: { name: string; slug: string } | null }[];
  }

  let { placeholder = "Search ideas, pain points, industries..." }: { placeholder?: string } = $props();

  let query = $state("");
  let results = $state<SearchResults | null>(null);
  let isLoading = $state(false);
  let isOpen = $state(false);
  let highlightedIndex = $state(-1);
  let inputEl: HTMLInputElement | undefined = $state(undefined);
  let containerEl: HTMLDivElement | undefined = $state(undefined);
  let debounceTimer: ReturnType<typeof setTimeout> | undefined;

  const hasResults = $derived(
    results && (results.categories.length > 0 || results.ideas.length > 0 || results.painPoints.length > 0)
  );

  const flatItems = $derived.by(() => {
    if (!results) return [];
    const items: { type: string; id: string; href: string }[] = [];
    for (const c of results.categories) {
      const href = !c.isParent && c.childCount === 0
        ? buildLeafCategoryListingUrl(c.slug, c.ideaCount, c.painPointCount)
        : `/catalog/categories/${c.slug}`;
      items.push({ type: "category", id: c.id, href });
    }
    for (const i of results.ideas) {
      items.push({ type: "idea", id: i.id, href: `/catalog/ideas/${i.id}` });
    }
    for (const pp of results.painPoints) {
      items.push({ type: "painPoint", id: pp.id, href: `/catalog/pain-points/${pp.id}` });
    }
    return items;
  });

  function handleInput() {
    clearTimeout(debounceTimer);
    const q = query.trim();
    if (q.length < 2) {
      results = null;
      isOpen = false;
      return;
    }
    isLoading = true;
    isOpen = true;
    debounceTimer = setTimeout(() => fetchResults(q), 250);
  }

  async function fetchResults(q: string) {
    try {
      const res = await fetch(`/api/catalog/search?q=${encodeURIComponent(q)}`);
      if (res.ok) {
        results = await res.json();
      }
    } catch {
      results = null;
    } finally {
      isLoading = false;
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (!isOpen) return;

    if (e.key === "Escape") {
      e.preventDefault();
      close();
      return;
    }

    if (e.key === "ArrowDown") {
      e.preventDefault();
      highlightedIndex = Math.min(highlightedIndex + 1, flatItems.length - 1);
      return;
    }

    if (e.key === "ArrowUp") {
      e.preventDefault();
      highlightedIndex = Math.max(highlightedIndex - 1, -1);
      return;
    }

    if (e.key === "Enter" && highlightedIndex >= 0 && flatItems[highlightedIndex]) {
      e.preventDefault();
      navigateTo(flatItems[highlightedIndex].href);
    }
  }

  function navigateTo(href: string) {
    close();
    goto(href);
  }

  function close() {
    isOpen = false;
    highlightedIndex = -1;
  }

  function handleClickOutside(e: MouseEvent) {
    if (containerEl && !containerEl.contains(e.target as Node)) {
      close();
    }
  }

  function clearQuery() {
    query = "";
    results = null;
    isOpen = false;
    inputEl?.focus();
  }

  function handleFocus() {
    if (query.trim().length >= 2 && results) {
      isOpen = true;
    }
  }

  // Track flat index for each section item
  function getFlatIndex(type: string, idx: number): number {
    if (!results) return -1;
    let offset = 0;
    if (type === "idea") offset = results.categories.length;
    if (type === "painPoint") offset = results.categories.length + results.ideas.length;
    return offset + idx;
  }
</script>

<svelte:document onclick={handleClickOutside} />

<div class="relative w-full" bind:this={containerEl}>
  <div class="relative">
    <Search class="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted pointer-events-none" />
    <input
      bind:this={inputEl}
      type="text"
      bind:value={query}
      oninput={handleInput}
      onkeydown={handleKeydown}
      onfocus={handleFocus}
      {placeholder}
      autocomplete="off"
      spellcheck={false}
      class="w-full pl-12 pr-10 py-3.5 text-base rounded-xl border border-border bg-bg-elevated text-text-primary placeholder:text-text-muted
        focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent
        shadow-sm transition-all"
    />
    {#if query}
      <button
        class="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-text-muted hover:text-text-primary transition-colors rounded-full hover:bg-bg-surface"
        onclick={clearQuery}
        aria-label="Clear search"
      >
        <X class="w-4 h-4" />
      </button>
    {/if}
  </div>

  <!-- Autocomplete dropdown -->
  {#if isOpen}
    <div class="absolute z-30 w-full mt-2 bg-bg-elevated border border-border rounded-xl shadow-lg overflow-hidden max-h-[420px] overflow-y-auto">
      {#if isLoading}
        <div class="flex items-center justify-center gap-2 py-8 text-text-muted">
          <Loader2 class="w-4 h-4 animate-spin" />
          <span class="text-sm">Searching...</span>
        </div>
      {:else if !hasResults && query.trim().length >= 2}
        <div class="py-8 text-center text-text-muted">
          <p class="text-sm">No results for "{query.trim()}"</p>
        </div>
      {:else if results}
        <!-- Categories -->
        {#if results.categories.length > 0}
          <div class="px-3 pt-3 pb-1">
            <span class="mono-label">Industries</span>
          </div>
          {#each results.categories as cat, i}
            {@const fi = getFlatIndex("category", i)}
            <button
              class="w-full text-left flex items-center gap-3 px-4 py-2.5 transition-colors
                {fi === highlightedIndex ? 'bg-accent/8 text-accent' : 'text-text-primary hover:bg-bg-surface'}"
              onclick={() => navigateTo(
                !cat.isParent && cat.childCount === 0
                  ? buildLeafCategoryListingUrl(cat.slug, cat.ideaCount, cat.painPointCount)
                  : `/catalog/categories/${cat.slug}`
              )}
              onmouseenter={() => (highlightedIndex = fi)}
            >
              <Folder class="w-4 h-4 shrink-0 text-text-muted" />
              <span class="flex-1 text-sm font-medium truncate">{cat.name}</span>
              {#if cat.isParent && cat.childCount > 0}
                <span class="text-xs text-text-muted">{cat.childCount} subcategories</span>
              {/if}
            </button>
          {/each}
        {/if}

        <!-- Ideas -->
        {#if results.ideas.length > 0}
          <div class="px-3 pt-3 pb-1 {results.categories.length > 0 ? 'border-t border-border' : ''}">
            <span class="mono-label">Ideas</span>
          </div>
          {#each results.ideas as idea, i}
            {@const fi = getFlatIndex("idea", i)}
            <button
              class="w-full text-left flex items-center gap-3 px-4 py-2.5 transition-colors
                {fi === highlightedIndex ? 'bg-accent/8 text-accent' : 'text-text-primary hover:bg-bg-surface'}"
              onclick={() => navigateTo(`/catalog/ideas/${idea.id}`)}
              onmouseenter={() => (highlightedIndex = fi)}
            >
              <Lightbulb class="w-4 h-4 shrink-0 text-text-muted" />
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium truncate">{idea.solution_name}</p>
                {#if idea.category}
                  <p class="text-xs text-text-muted truncate">{idea.category.name}</p>
                {/if}
              </div>
            </button>
          {/each}
        {/if}

        <!-- Pain Points -->
        {#if results.painPoints.length > 0}
          <div class="px-3 pt-3 pb-1 {(results.categories.length > 0 || results.ideas.length > 0) ? 'border-t border-border' : ''}">
            <span class="mono-label">Pain Points</span>
          </div>
          {#each results.painPoints as pp, i}
            {@const fi = getFlatIndex("painPoint", i)}
            <button
              class="w-full text-left flex items-center gap-3 px-4 py-2.5 transition-colors
                {fi === highlightedIndex ? 'bg-accent/8 text-accent' : 'text-text-primary hover:bg-bg-surface'}"
              onclick={() => navigateTo(`/catalog/pain-points/${pp.id}`)}
              onmouseenter={() => (highlightedIndex = fi)}
            >
              <AlertCircle class="w-4 h-4 shrink-0 text-text-muted" />
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium truncate">{pp.title}</p>
                {#if pp.category}
                  <p class="text-xs text-text-muted truncate">{pp.category.name}</p>
                {/if}
              </div>
            </button>
          {/each}
        {/if}
      {/if}
    </div>
  {/if}
</div>
