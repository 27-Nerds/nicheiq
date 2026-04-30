<script lang="ts">
  import ProgressRing from "$lib/components/ui/ProgressRing.svelte";
  import CategoryBadge from "$lib/components/catalog/CategoryBadge.svelte";
  import { fly } from "svelte/transition";

  let { painPoint, index = 0, href, onclick, hideCategory = false }: { painPoint: any; index?: number; href: string; onclick?: (e: MouseEvent) => void; hideCategory?: boolean } = $props();

  const wtpPercent = $derived(
    painPoint.willingnessToPayScore != null
      ? Math.round(painPoint.willingnessToPayScore * 100)
      : null
  );
</script>

<a
  {href}
  {onclick}
  class="block w-full text-left card card-sm group"
  in:fly={{ y: 12, duration: 400, delay: index * 40 }}
>
  <div class="flex gap-3">
    <div class="shrink-0 flex flex-col items-center pt-0.5">
      <ProgressRing
        value={painPoint.severityScore ?? 0}
        size={44}
        showValue={true}
        color="auto"
        animate={false}
        showTooltip={false}
        flat={true}
      />
    </div>

    <div class="flex-1 min-w-0">
      <h3 class="font-semibold text-text-primary group-hover:text-accent transition-colors text-sm leading-tight truncate-2">
        {painPoint.title}
      </h3>

      <p class="text-xs text-text-secondary mt-1.5 truncate-2">{painPoint.description}</p>

      {#if wtpPercent != null}
        <div class="mt-2">
          <span class="text-xs text-text-secondary">{wtpPercent}%</span>
          <span class="mono-label ml-0.5" style="font-size: 0.55rem;">WTP</span>
        </div>
      {/if}

      {#if painPoint.category && !hideCategory}
        <div class="mt-1.5">
          <CategoryBadge category={painPoint.category} type="pain-points" light asLink={false} />
        </div>
      {/if}
    </div>
  </div>
</a>
