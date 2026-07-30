<script lang="ts">
  import type { StageCosts } from "$lib/types/job";
  interface Props {
    stageCosts: StageCosts;
    guided?: boolean;
  }

  let { stageCosts, guided = false }: Props = $props();
  const guidedCosts = $derived(stageCosts.guided);
  const credits = (value: number) => `${value} ${value === 1 ? "credit" : "credits"}`;
</script>

<div class="flex flex-wrap items-center justify-center gap-x-1.5 gap-y-1 text-xs">
  {#if guided && guidedCosts}
    <div class="flex items-center gap-1">
      <span class="w-2 h-2 rounded-full bg-accent-hover shrink-0"></span>
      <span class="text-text-secondary font-medium">Validate the niche</span>
      <span class="font-mono tabular-nums text-text-muted">{credits(guidedCosts.s1)} now</span>
    </div>

    <span class="text-text-muted/40 hidden sm:inline">—</span>

    <div class="flex items-center gap-1">
      <span class="w-2 h-2 rounded-full bg-border shrink-0"></span>
      <span class="text-text-muted">Evidence + audience</span>
      <span class="font-mono tabular-nums text-text-muted/60">{credits(guidedCosts.s2_4)} after approval</span>
    </div>

    <span class="text-text-muted/40 hidden sm:inline">—</span>

    <div class="flex items-center gap-1">
      <span class="w-2 h-2 rounded-full bg-border shrink-0"></span>
      <span class="text-text-muted">Generate ideas</span>
      <span class="font-mono tabular-nums text-text-muted/60">{credits(guidedCosts.s5)} after approval</span>
    </div>

    <span class="text-text-muted/40 hidden sm:inline">—</span>

    <div class="flex items-center gap-1">
      <span class="w-2 h-2 rounded-full bg-border shrink-0"></span>
      <span class="text-text-muted">Pick + Deep Research</span>
      <span class="font-mono tabular-nums text-text-muted/60">{credits(stageCosts.deep_research)} later</span>
    </div>
  {:else}
    <!-- Step 1: Discover -->
    <div class="flex items-center gap-1">
      <span class="w-2 h-2 rounded-full bg-accent-hover shrink-0"></span>
      <span class="text-text-secondary font-medium">Discover 5–10 scored ideas</span>
      <span class="font-mono tabular-nums text-text-muted">{stageCosts.discovery} credits · ~15 min</span>
    </div>

    <span class="text-text-muted/40 hidden sm:inline">—</span>

    <!-- Step 2: Pick -->
    <div class="flex items-center gap-1">
      <span class="w-2 h-2 rounded-full bg-border shrink-0"></span>
      <span class="text-text-muted">You pick the best</span>
      <span class="font-mono tabular-nums text-text-muted/60">free</span>
    </div>

    <span class="text-text-muted/40 hidden sm:inline">—</span>

    <!-- Step 3: Validate -->
    <div class="flex items-center gap-1">
      <span class="w-2 h-2 rounded-full bg-border shrink-0"></span>
      <span class="text-text-muted">Full validation</span>
      <span class="font-mono tabular-nums text-text-muted/60">{stageCosts.deep_research} credits · ~20 min</span>
    </div>
  {/if}
</div>
