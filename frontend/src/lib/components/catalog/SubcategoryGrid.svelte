<script lang="ts">
  import { ChevronDown } from "lucide-svelte";
  import IndustryCard from "./IndustryCard.svelte";
  import { splitChildren } from "$lib/utils/catalog-utils";

  const MAX_COLS = 4; // matches xl:grid-cols-4

  interface Child {
    name: string;
    slug: string;
    _count?: { ideas: number; painPoints: number };
    [key: string]: any;
  }

  let {
    children,
    emptyMode = "toggle",
    emptyLinkHref = "",
    cardHref,
    showAll = false,
  }: {
    children: Child[];
    emptyMode?: "link" | "toggle";
    emptyLinkHref?: string;
    cardHref?: (child: Child) => string;
    showAll?: boolean;
  } = $props();

  let showEmpty = $state(false);

  const { populated, empty } = $derived(splitChildren(children));

  // How many empty cards to show: complete the last row + ensure at least one full row
  const fillCount = $derived.by(() => {
    // Complete the last row of populated cards
    const rowFill = populated.length > 0 && populated.length % MAX_COLS !== 0
      ? MAX_COLS - (populated.length % MAX_COLS)
      : 0;
    // Ensure at least one full row is always visible
    const minFill = Math.max(MAX_COLS - populated.length, 0);
    return Math.min(Math.max(rowFill, minFill), empty.length);
  });

  const fillEmpty = $derived(empty.slice(0, fillCount));
  const remainingEmpty = $derived(empty.slice(fillCount));

  // Single merged list: populated + row-fill (collapsed) or all empty (expanded)
  const visibleItems = $derived(
    showAll
      ? children
      : showEmpty
        ? [...populated, ...empty]
        : [...populated, ...fillEmpty]
  );

  function toggle() {
    showEmpty = !showEmpty;
  }
</script>

{#if visibleItems.length > 0}
  <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
    {#each visibleItems as child, i (child.slug)}
      <IndustryCard category={child} href={cardHref?.(child)} index={i} />
    {/each}
  </div>
{/if}

<!-- Empty indicator pill -->
{#if !showAll && remainingEmpty.length > 0}
  <div class="mt-3">
    {#if emptyMode === "link"}
      <a
        href={emptyLinkHref}
        class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-full
               bg-bg-surface border border-border text-text-muted
               hover:text-accent hover:border-accent/30 transition-colors"
      >
        {#if populated.length > 0}
          +{remainingEmpty.length} more {remainingEmpty.length === 1 ? 'subcategory' : 'subcategories'}
        {:else}
          {remainingEmpty.length} {remainingEmpty.length === 1 ? 'subcategory' : 'subcategories'} &middot; no items yet
        {/if}
      </a>
    {:else}
      <button
        onclick={toggle}
        class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-full
               bg-bg-surface border border-border text-text-muted
               hover:text-accent hover:border-accent/30 transition-colors"
      >
        {showEmpty ? 'Hide' : `Show ${remainingEmpty.length}`} empty {remainingEmpty.length === 1 ? 'subcategory' : 'subcategories'}
        <ChevronDown class="w-3.5 h-3.5 transition-transform duration-200 {showEmpty ? 'rotate-180' : ''}" />
      </button>
    {/if}
  </div>
{/if}
