<script lang="ts">
  import Badge from "$lib/components/ui/Badge.svelte";
  import ProgressRing from "$lib/components/ui/ProgressRing.svelte";
  import CategoryBadge from "$lib/components/catalog/CategoryBadge.svelte";
  import { ArrowRight } from "lucide-svelte";
  import { fly } from "svelte/transition";
  import { getSuperpower, computeCompositeScore, SOLUTION_PREVIEW_KEYS } from "$lib/utils/superpower";

  let { idea, index = 0, href, onclick }: { idea: any; index?: number; href: string; onclick?: (e: MouseEvent) => void } = $props();

  const compositeScore = $derived(computeCompositeScore(idea, SOLUTION_PREVIEW_KEYS));
  const superpower = $derived(getSuperpower(idea, SOLUTION_PREVIEW_KEYS));
</script>

<a
  {href}
  {onclick}
  class="block w-full text-left card card-interactive card-sm group idea-card"
  in:fly={{ y: 12, duration: 400, delay: index * 40 }}
>
  <div class="flex gap-3">
    <!-- Score hero -->
    <div class="shrink-0 flex flex-col items-center pt-0.5">
      <ProgressRing
        value={compositeScore}
        size={44}
        showValue={true}
        color="auto"
        animate={false}
        showTooltip={false}
        flat={true}
      />
    </div>

    <!-- Content -->
    <div class="flex-1 min-w-0">
      <!-- Title + Featured badge -->
      <h3 class="text-sm font-semibold text-text-primary leading-tight truncate-2 group-hover:text-accent transition-colors">
        {idea.solution_name}
        {#if idea.is_featured}
          <Badge variant="accent" size="sm">Featured</Badge>
        {/if}
      </h3>

      {#if idea.project_type}
        <div class="flex items-center gap-1.5 mt-1 flex-wrap">
          <span class="text-xs px-2 py-0.5 rounded-full bg-bg-elevated border border-border text-text-muted">
            {idea.project_type}
          </span>
        </div>
      {:else}
        <div class="mt-1" style="height: 1.375rem;"></div>
      {/if}

      <!-- Description (clamped to 2 lines) -->
      <p class="mt-1.5 text-xs text-text-secondary leading-normal truncate-2">
        {idea.description}
      </p>

      <!-- Stat row -->
      <div class="flex items-center gap-4 mt-2">
        {#if idea.market_fit_score != null}
          <div>
            <span class="mono-label">Fit</span>
            <span class="text-xs font-medium text-text-primary ml-1">
              {(idea.market_fit_score * 100).toFixed(0)}%
            </span>
          </div>
        {/if}
        {#if idea.novelty_score != null}
          <div>
            <span class="mono-label">Novel</span>
            <span class="text-xs font-medium text-text-primary ml-1">
              {(idea.novelty_score * 100).toFixed(0)}%
            </span>
          </div>
        {/if}
        {#if superpower}
          <span class="superpower-tag superpower-tag-{superpower.variant}">{superpower.label}</span>
        {/if}
      </div>

      {#if idea.category}
        <div class="mt-1.5">
          <CategoryBadge category={idea.category} type="ideas" light asLink={false} />
        </div>
      {/if}

      <span class="mt-1.5 inline-flex items-center gap-1 text-xs text-text-muted opacity-0 group-hover:opacity-100 transition-opacity">
        View details <ArrowRight class="w-3 h-3" />
      </span>
    </div>
  </div>
</a>

<style>
  .idea-card:hover {
    transform: translateY(-2px);
    border-bottom: 1px solid var(--color-accent);
  }

  .superpower-tag {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    line-height: 1.2;
    padding-left: 0.5rem;
    border-left: 2px solid currentColor;
  }
  .superpower-tag-success { color: var(--color-success-dark); }
  .superpower-tag-accent { color: var(--color-accent-dark); }
  .superpower-tag-info { color: var(--color-secondary-dark); }
  .superpower-tag-warning { color: var(--color-warning-dark); }
</style>
