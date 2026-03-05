<script lang="ts">
  import { fade, fly } from "svelte/transition";
  import { portal } from "$lib/actions/portal";
  import CategoryAccordion from "./CategoryAccordion.svelte";
  import type { CategoryGroup } from "./CategoryAccordion.svelte";

  interface Props {
    open: boolean;
    categories: CategoryGroup[];
    activeCategory: string;
    allLabel: string;
    onSelect: (slug: string) => void;
    onClose: () => void;
    grouped?: boolean;
    countField?: 'ideas' | 'painPoints';
  }

  let {
    open,
    categories,
    activeCategory,
    allLabel,
    onSelect,
    onClose,
    grouped = false,
    countField,
  }: Props = $props();

  // Lock body scroll when open
  $effect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
      return () => {
        document.body.style.overflow = "";
      };
    }
  });

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    }
  }

  function handleSelect(slug: string) {
    onSelect(slug);
    onClose();
  }
</script>

<svelte:window onkeydown={open ? handleKeydown : undefined} />

{#if open}
  <!-- Portal to body to escape container constraints -->
  <div use:portal>
    <!-- Backdrop -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div
      class="fixed inset-0 z-40 bg-black/50"
      transition:fade={{ duration: 200 }}
      onclick={onClose}
      onkeydown={handleKeydown}
    >
      <!-- Sheet -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div
        class="absolute bottom-0 left-0 right-0 bg-bg-surface rounded-t-2xl max-h-[70vh] flex flex-col"
        transition:fly={{ y: 300, duration: 300 }}
        onclick={(e) => e.stopPropagation()}
        onkeydown={(e) => e.stopPropagation()}
      >
        <!-- Handle bar -->
        <div class="flex justify-center pt-3 pb-2 flex-shrink-0">
          <div class="w-10 h-1 rounded-full bg-border"></div>
        </div>

        <!-- Header -->
        <div class="px-4 pb-3 border-b border-border flex-shrink-0">
          <h3 class="text-sm font-semibold text-text-primary">Categories</h3>
        </div>

        <!-- Scrollable accordion content -->
        <div class="overflow-y-auto px-4 py-3">
          <CategoryAccordion
            {categories}
            {activeCategory}
            {allLabel}
            onSelect={handleSelect}
            touchFriendly={true}
            {grouped}
            {countField}
          />
        </div>
      </div>
    </div>
  </div>
{/if}
