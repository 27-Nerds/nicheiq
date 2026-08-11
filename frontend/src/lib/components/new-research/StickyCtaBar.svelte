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
    priceAvailable?: boolean;
    stageName?: string;
    ctaLabel?: string;
  }

  let {
    visible,
    niche,
    creditCost,
    loading,
    disabled,
    hasCredits,
    stageCost,
    priceAvailable = true,
    stageName = "discovery",
    ctaLabel = "Discover ideas",
  }: Props = $props();

  const truncatedNiche = $derived(
    niche.length > 40 ? niche.slice(0, 40) + "\u2026" : niche,
  );
  const priceDetail = $derived(
    stageName === "guided research"
      ? `${creditCost} ${creditCost === 1 ? "credit" : "credits"} · niche checkpoint first`
      : `${creditCost} ${creditCost === 1 ? "credit" : "credits"} · usually under 1 hour`,
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
        <span class="text-xs font-mono tabular-nums text-text-muted">
          {priceAvailable ? priceDetail : "Pricing unavailable"}
        </span>
      </div>

    </div>
    {#if !priceAvailable}
      <button type="button" disabled class="sticky-cta-button btn-primary shrink-0 flex items-center gap-2 px-5 py-2.5 text-sm">
        Pricing unavailable
      </button>
    {:else if hasCredits}
      <button
        type="submit"
        disabled={disabled || loading}
        class="sticky-cta-button btn-primary shrink-0 flex items-center gap-2 px-5 py-2.5 text-sm"
      >
        {#if loading}
          <Loader2 class="w-4 h-4 animate-spin" />
          Analyzing your topic...
        {:else}
          {ctaLabel}
          <ArrowRight class="w-4 h-4" />
        {/if}
      </button>
    {:else}
      <button
        type="button"
        onclick={() => creditTopUp.show({ balance: (page.data.creditBalance as number) ?? 0, required: stageCost, stageName })}
        class="btn-primary shrink-0 flex items-center gap-2 px-5 py-2.5 text-sm"
      >
        <Coins class="w-4 h-4" />
        Get {stageCost} {stageCost === 1 ? "Credit" : "Credits"}
      </button>
    {/if}
  </div>
</div>
<style>
  .sticky-cta-button:disabled {
    border: 1px solid var(--color-border);
    background: var(--color-bg-elevated);
    color: var(--color-text-muted);
    cursor: not-allowed;
    opacity: 1;
  }
</style>
