<script lang="ts">
  import { ArrowRight, Loader2, Coins } from "lucide-svelte";
  import { page } from "$app/state";
  import { creditTopUp } from "$lib/stores/creditTopUp.svelte";

  interface Props {
    visible: boolean;
    niche: string;
    creditCost: number;
    loading: boolean;
    disabled: boolean;
    hasCredits: boolean;
    stageCost: number;
  }

  let { visible, niche, creditCost, loading, disabled, hasCredits, stageCost }: Props = $props();

  const truncatedNiche = $derived(
    niche.length > 40 ? niche.slice(0, 40) + "\u2026" : niche,
  );
</script>

<div
  class="fixed bottom-0 left-0 right-0 z-40 border-t border-border bg-bg-surface/95 backdrop-blur-sm
    transition-transform duration-300 ease-out
    {visible ? 'translate-y-0' : 'translate-y-[calc(100%+1px)] pointer-events-none'}"
>
  <div class="max-w-3xl mx-auto px-4 sm:px-6 py-3 flex items-center gap-3">
    <div class="flex-1 min-w-0">
      {#if niche.trim()}
        <p class="text-sm text-text-secondary truncate">{truncatedNiche}</p>
      {:else}
        <p class="text-sm text-text-muted">Enter a topic to get started</p>
      {/if}
      <div class="flex items-center gap-1.5 mt-0.5">
        <Coins class="w-3 h-3 text-accent" />
        <span class="text-xs font-mono tabular-nums text-text-muted"
          >{creditCost} credits · ~5 min</span
        >
      </div>
    </div>
    {#if hasCredits}
      <button
        type="submit"
        disabled={disabled || loading}
        class="btn-primary shrink-0 flex items-center gap-2 px-5 py-2.5 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {#if loading}
          <Loader2 class="w-4 h-4 animate-spin" />
          Analyzing your topic...
        {:else}
          Discover ideas
          <ArrowRight class="w-4 h-4" />
        {/if}
      </button>
    {:else}
      <button
        type="button"
        onclick={() => creditTopUp.show({ balance: (page.data.creditBalance as number) ?? 0, required: stageCost, stageName: 'discovery' })}
        class="btn-primary shrink-0 flex items-center gap-2 px-5 py-2.5 text-sm"
      >
        <Coins class="w-4 h-4" />
        Get {stageCost} Credits
      </button>
    {/if}
  </div>
</div>
