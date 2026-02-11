<script lang="ts">
  import {
    ChevronDown,
    ChevronUp,
    CheckCircle,
    Circle,
  } from "lucide-svelte";
  import Badge from "$lib/components/ui/Badge.svelte";
  import ProgressBar from "$lib/components/ui/ProgressBar.svelte";
  import type { SolutionPreview } from "$lib/types/job";
  import { renderTechnicalContent } from "$lib/utils/format";

  interface Props {
    solution: SolutionPreview;
    onSelect: (name: string) => void;
    disabled?: boolean;
    isSelected?: boolean;
    maxReached?: boolean;
  }

  let {
    solution,
    onSelect,
    disabled = false,
    isSelected = false,
    maxReached = false,
  }: Props = $props();

  let expanded = $state(false);

  const scores = $derived([
    { label: "Market Fit", value: solution.market_fit_score },
    { label: "Feasibility", value: solution.technical_feasibility_score },
    { label: "SEO Potential", value: solution.seo_scalability_score },
    { label: "Novelty", value: solution.novelty_score },
    { label: "Solo Dev", value: solution.solo_dev_feasibility },
  ]);

  // Extract just the duration part from dev time (e.g., "6-8 weeks" from "6-8 weeks for MVP...")
  const devTimeParsed = $derived.by(() => {
    const devTime = solution.estimated_development_time;
    if (!devTime) return null;
    const match = devTime.match(/^[\d\-\+]+\s*(?:weeks?|months?|days?)/i);
    if (match) return { short: match[0], full: devTime };
    if (devTime.length <= 20) return { short: devTime, full: devTime };
    return { short: devTime.slice(0, 17) + "...", full: devTime };
  });

  // Card is clickable to toggle selection (unless disabled or max reached and not selected)
  const isToggleable = $derived(!disabled && (isSelected || !maxReached));

  function handleCardClick() {
    if (isToggleable) {
      onSelect(solution.solution_name);
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if ((e.key === 'Enter' || e.key === ' ') && isToggleable) {
      e.preventDefault();
      onSelect(solution.solution_name);
    }
  }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class="card relative border-l-2 transition-all duration-200
    {isSelected
      ? 'border-l-accent ring-2 ring-accent/20'
      : isToggleable
        ? 'border-l-border hover:border-l-accent/50 cursor-pointer'
        : 'border-l-border opacity-60'}"
  role="option"
  aria-selected={isSelected}
  aria-label="Solution: {solution.solution_name}"
  tabindex={isToggleable ? 0 : -1}
  onclick={handleCardClick}
  onkeydown={handleKeydown}
>
  <!-- Header with checkbox -->
  <div class="flex items-start justify-between gap-3">
    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-2">
        <h3 class="text-base font-semibold text-text-primary truncate">
          {solution.solution_name}
        </h3>
        {#if isSelected}
          <Badge variant="accent" size="sm">Selected</Badge>
        {/if}
      </div>
      {#if solution.project_type}
        <Badge size="sm" class="mt-1">{solution.project_type}</Badge>
      {/if}
    </div>

    <!-- Selection checkbox indicator -->
    <div class="shrink-0 mt-0.5">
      {#if isSelected}
        <CheckCircle class="w-5 h-5 text-accent" />
      {:else if isToggleable}
        <Circle class="w-5 h-5 text-text-muted" />
      {:else}
        <Circle class="w-5 h-5 text-text-muted/40" />
      {/if}
    </div>
  </div>

  <!-- Description -->
  <p class="mt-2 text-sm text-text-secondary">
    {solution.description}
  </p>

  <!-- Value Proposition -->
  <p class="mt-1.5 text-sm text-text-muted italic">
    {solution.value_proposition}
  </p>

  <!-- Score Grid -->
  <div class="mt-4 grid grid-cols-2 sm:grid-cols-5 gap-x-3 gap-y-4">
    {#each scores as score}
      <div>
        <div class="min-w-0">
          <div class="mono-label">{score.label}</div>
          <div class="flex items-center gap-1">
            <ProgressBar value={score.value ?? 0} showValue={false} />
            <span class="text-xs font-mono text-text-muted shrink-0">
              {score.value != null ? (score.value * 100).toFixed(0) : "--"}
            </span>
          </div>
        </div>
      </div>
    {/each}
  </div>

  <!-- Dev Time -->
  {#if devTimeParsed}
    <div class="mt-2 flex items-center gap-1.5 text-xs text-text-muted" title={devTimeParsed.full}>
      <span>&#9201;</span>
      <span>{devTimeParsed.short} MVP</span>
    </div>
  {/if}

  <!-- Expandable Details -->
  <button
    type="button"
    class="mt-3 flex items-center gap-1 text-xs text-text-muted hover:text-text-secondary hover:bg-bg-hover rounded px-2 py-1 transition-colors"
    onclick={(e) => { e.stopPropagation(); expanded = !expanded; }}
  >
    {#if expanded}
      <ChevronUp class="w-3.5 h-3.5" />
      Show less
    {:else}
      <ChevronDown class="w-3.5 h-3.5" />
      Show more
    {/if}
  </button>

  {#if expanded}
    <div class="mt-3 space-y-4 text-sm border-t border-border pt-3">
      {#if solution.pricing_strategy}
        <div>
          <h4 class="mono-label mb-1">Pricing Strategy</h4>
          <p class="text-text-secondary">{solution.pricing_strategy}</p>
        </div>
      {/if}

      {#if solution.conventional_approach || solution.innovation_angle || solution.why_it_works}
        <div>
          <h4 class="mono-label mb-2">Innovation Breakdown</h4>
          <div class="space-y-2">
            {#if solution.conventional_approach}
              <div class="rounded border border-border px-3 py-2">
                <span class="text-xs font-medium uppercase tracking-wider text-text-muted">Conventional Path</span>
                <p class="mt-0.5 text-text-secondary">{solution.conventional_approach}</p>
              </div>
            {/if}
            {#if solution.innovation_angle}
              <div class="rounded border border-accent/30 bg-accent/5 px-3 py-2">
                <span class="text-xs font-medium uppercase tracking-wider text-accent">What's Different</span>
                <p class="mt-0.5 text-text-secondary">{solution.innovation_angle}</p>
              </div>
            {/if}
            {#if solution.why_it_works}
              <div class="rounded border border-border px-3 py-2">
                <span class="text-xs font-medium uppercase tracking-wider text-text-muted">Why It Works</span>
                <p class="mt-0.5 text-text-secondary">{solution.why_it_works}</p>
              </div>
            {/if}
          </div>
        </div>
      {/if}

      {#if solution.pain_points_addressed && solution.pain_points_addressed.length > 0}
        <div>
          <h4 class="mono-label mb-1">Pain Points Addressed</h4>
          <ul class="space-y-0.5">
            {#each solution.pain_points_addressed as point}
              <li class="text-text-secondary flex items-start gap-1.5">
                <span class="text-accent mt-1 shrink-0">-</span>
                {point}
              </li>
            {/each}
          </ul>
        </div>
      {/if}

      {#if solution.core_features && solution.core_features.length > 0}
        <div>
          <h4 class="mono-label mb-1">Core Features</h4>
          <ul class="space-y-0.5">
            {#each solution.core_features as feature}
              <li class="text-text-secondary flex items-start gap-1.5">
                <span class="text-accent mt-1 shrink-0">-</span>
                {feature}
              </li>
            {/each}
          </ul>
        </div>
      {/if}

      {#if solution.differentiation_factors && solution.differentiation_factors.length > 0}
        <div>
          <h4 class="mono-label mb-1">Differentiation</h4>
          <ul class="space-y-0.5">
            {#each solution.differentiation_factors as factor}
              <li class="text-text-secondary flex items-start gap-1.5">
                <span class="text-accent mt-1 shrink-0">-</span>
                {factor}
              </li>
            {/each}
          </ul>
        </div>
      {/if}

      {#if solution.target_personas && solution.target_personas.length > 0}
        <div>
          <h4 class="mono-label mb-1">Target Personas</h4>
          <ul class="space-y-0.5">
            {#each solution.target_personas as persona}
              <li class="text-text-secondary flex items-start gap-1.5">
                <span class="text-accent mt-1 shrink-0">-</span>
                {persona}
              </li>
            {/each}
          </ul>
        </div>
      {/if}

      {#if solution.programmatic_seo_opportunity}
        <div>
          <h4 class="mono-label mb-1">Programmatic SEO Opportunity</h4>
          <div class="markdown-content markdown-content-compact text-text-secondary text-sm">
            {@html renderTechnicalContent(solution.programmatic_seo_opportunity)}
          </div>
        </div>
      {/if}

      {#if solution.estimated_cac_organic}
        <div>
          <h4 class="mono-label mb-1">Estimated CAC</h4>
          <p class="text-text-secondary">
            {solution.estimated_cac_organic}{#if solution.estimated_cac_paid} <span class="text-text-muted">(vs {solution.estimated_cac_paid} paid)</span>{/if}
          </p>
        </div>
      {/if}

      {#if solution.organic_discovery_queries && solution.organic_discovery_queries.length > 0}
        <div>
          <h4 class="mono-label mb-1">Organic Discovery Queries</h4>
          <div class="flex flex-wrap gap-1.5">
            {#each solution.organic_discovery_queries as query}
              <span
                class="text-xs px-2 py-0.5 rounded bg-bg-elevated border border-border text-text-secondary"
              >
                {query}
              </span>
            {/each}
          </div>
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .markdown-content-compact :global(h1),
  .markdown-content-compact :global(h2),
  .markdown-content-compact :global(h3),
  .markdown-content-compact :global(h4) {
    margin-top: 0.75rem;
    margin-bottom: 0.25rem;
    font-size: 0.875rem;
  }
  .markdown-content-compact :global(p) {
    margin-bottom: 0.5rem;
  }
  .markdown-content-compact :global(ul),
  .markdown-content-compact :global(ol) {
    margin-bottom: 0.5rem;
  }
</style>
