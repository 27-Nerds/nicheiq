<script lang="ts">
  import { ArrowRight, Folder, FolderOpen } from "lucide-svelte";
  import { fly } from "svelte/transition";
  import { formatItemCounts } from "$lib/utils/catalog-utils";

  interface Category {
    name: string;
    slug: string;
    children?: any[];
    _count?: { ideas: number; painPoints: number };
  }

  let { category, index = 0, totalItems = 0, href }: { category: Category; index?: number; totalItems?: number; href?: string } = $props();

  const childCount = $derived(category.children?.length ?? 0);
  const isLeaf = $derived(childCount === 0);
  const ideaCount = $derived(category._count?.ideas ?? 0);
  const painPointCount = $derived(category._count?.painPoints ?? 0);
  const computedTotalItems = $derived(totalItems || (ideaCount + painPointCount));
  const isEmpty = $derived(computedTotalItems === 0);
  const resolvedHref = $derived(href ?? `/catalog/categories/${category.slug}`);
</script>

<a
  href={resolvedHref}
  class="block card card-interactive card-sm group {isEmpty ? 'industry-card-empty' : 'industry-card'}"
  in:fly={{ y: 12, duration: 400, delay: index * 30 }}
>
  <div class="flex items-start gap-3">
    <div class="shrink-0 w-9 h-9 rounded-lg flex items-center justify-center mt-0.5 {isEmpty ? 'bg-bg-surface' : 'bg-accent/8'}">
      {#if isEmpty}
        <FolderOpen class="w-4.5 h-4.5 text-text-muted" />
      {:else}
        <Folder class="w-4.5 h-4.5 text-accent" />
      {/if}
    </div>
    <div class="flex-1 min-w-0">
      <h3 class="text-sm font-semibold leading-tight transition-colors {isEmpty ? 'text-text-muted' : 'text-text-primary group-hover:text-accent'}">
        {category.name}
      </h3>
      {#if isLeaf}
        <p class="text-xs mt-1 {isEmpty ? 'text-text-muted italic' : 'text-text-muted'}">
          {formatItemCounts(ideaCount, painPointCount)}
        </p>
      {:else}
        <p class="text-xs text-text-muted mt-0.5">
          {childCount} {childCount === 1 ? 'subcategory' : 'subcategories'}
        </p>
        {#if computedTotalItems > 0}
          <p class="text-xs text-text-secondary mt-1">
            {computedTotalItems} {computedTotalItems === 1 ? 'item' : 'items'}
          </p>
        {:else}
          <p class="text-xs text-text-muted italic mt-1">No items yet</p>
        {/if}
      {/if}
    </div>
    {#if !isEmpty}
      <span class="shrink-0 text-text-muted opacity-0 group-hover:opacity-100 transition-opacity mt-2">
        <ArrowRight class="w-4 h-4" />
      </span>
    {/if}
  </div>
</a>

<style>
  .industry-card:hover {
    transform: translateY(-1px);
    border-bottom: 1px solid var(--color-accent);
  }

  .industry-card-empty:hover {
    transform: none;
    border-bottom-color: var(--color-border);
  }
</style>
