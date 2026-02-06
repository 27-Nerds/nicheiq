<script lang="ts">
  import { slide } from "svelte/transition";
  import { Plus, Minus } from "lucide-svelte";
  import type { Snippet } from "svelte";

  interface Props {
    title: string;
    open?: boolean;
    class?: string;
    children: Snippet;
  }

  let {
    title,
    open = $bindable(false),
    class: className = "",
    children,
  }: Props = $props();
</script>

<div class="border-b border-border {className}">
  <button
    onclick={() => (open = !open)}
    class="w-full flex items-center justify-between py-6 text-left group transition-colors duration-200"
  >
    <span
      class="font-display text-lg font-medium text-text-primary group-hover:text-accent transition-colors"
      >{title}</span
    >
    {#if open}
      <div
        class="w-8 h-8 rounded-lg bg-accent/10 border border-accent/50 flex items-center justify-center flex-shrink-0"
      >
        <Minus class="w-4 h-4 text-accent" />
      </div>
    {:else}
      <div
        class="w-8 h-8 rounded-lg bg-bg-surface border border-border flex items-center justify-center flex-shrink-0 group-hover:border-border-emphasis transition-colors"
      >
        <Plus
          class="w-4 h-4 text-text-muted group-hover:text-text-primary transition-colors"
        />
      </div>
    {/if}
  </button>

  {#if open}
    <div transition:slide={{ duration: 300 }} class="pb-6">
      <div class="text-text-secondary leading-relaxed pl-0">
        {@render children()}
      </div>
    </div>
  {/if}
</div>
