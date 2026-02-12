<script lang="ts">
  import {
    CheckCircle,
    Circle,
    ArrowRight,
  } from "lucide-svelte";
  import Badge from "$lib/components/ui/Badge.svelte";
  import ProgressRing from "$lib/components/ui/ProgressRing.svelte";
  import type { SolutionPreview } from "$lib/types/job";

  interface Props {
    solution: SolutionPreview;
    onSelect: (name: string) => void;
    onOpen: () => void;
    disabled?: boolean;
    isSelected?: boolean;
    maxReached?: boolean;
    isNew?: boolean;
  }

  let {
    solution,
    onSelect,
    onOpen,
    disabled = false,
    isSelected = false,
    maxReached = false,
    isNew = false,
  }: Props = $props();

  // Composite score for ProgressRing (0-1)
  const compositeScore = $derived.by(() => {
    if (solution.adjusted_composite_score != null) return solution.adjusted_composite_score;
    const vals = [
      solution.market_fit_score ?? 0,
      solution.technical_feasibility_score ?? 0,
      solution.seo_scalability_score ?? 0,
      solution.novelty_score ?? 0,
      solution.solo_dev_feasibility ?? 0,
    ];
    return vals.reduce((a, b) => a + b, 0) / vals.length;
  });

  // Superpower badge — based on highest score attribute
  const SUPERPOWER_MAP: Record<string, { label: string; variant: "success" | "accent" | "info" | "warning" }> = {
    market_fit_score: { label: "Market Fit", variant: "success" },
    seo_scalability_score: { label: "SEO Power", variant: "accent" },
    novelty_score: { label: "Innovator", variant: "info" },
    technical_feasibility_score: { label: "Quick Build", variant: "warning" },
    solo_dev_feasibility: { label: "Solo-Friendly", variant: "success" },
  };

  const superpower = $derived.by(() => {
    const entries: [string, number][] = [
      ["market_fit_score", solution.market_fit_score ?? 0],
      ["seo_scalability_score", solution.seo_scalability_score ?? 0],
      ["novelty_score", solution.novelty_score ?? 0],
      ["technical_feasibility_score", solution.technical_feasibility_score ?? 0],
      ["solo_dev_feasibility", solution.solo_dev_feasibility ?? 0],
    ];
    entries.sort((a, b) => b[1] - a[1]);
    return SUPERPOWER_MAP[entries[0][0]];
  });

  // Selection pulse micro-interaction
  let justSelected = $state(false);

  // Card is selectable (checkbox toggle)
  const isToggleable = $derived(!disabled && (isSelected || !maxReached));

  function handleCardClick() {
    onOpen();
  }

  function handleCheckboxClick(e: MouseEvent) {
    e.stopPropagation();
    if (!isToggleable) return;
    if (!isSelected) {
      justSelected = true;
      setTimeout(() => { justSelected = false; }, 300);
    }
    onSelect(solution.solution_name);
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onOpen();
    }
  }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class="card compact-card group p-3 relative transition-all duration-200 cursor-pointer
    {isSelected ? 'card-selected' : ''}
    {justSelected ? 'selection-pulse' : ''}
    {disabled && !isSelected ? 'opacity-60 cursor-default' : ''}"
  role="option"
  aria-selected={isSelected}
  aria-label="Solution: {solution.solution_name}"
  tabindex={0}
  onclick={handleCardClick}
  onkeydown={handleKeydown}
>
  <div class="flex gap-3">
    <!-- Score hero -->
    <div class="shrink-0 flex flex-col items-center pt-0.5">
      <ProgressRing value={compositeScore} size={44} showValue={true} color="auto" animate={false} showTooltip={false} flat={true} />
    </div>

    <!-- Content -->
    <div class="flex-1 min-w-0">
      <!-- Title + Checkbox -->
      <div class="flex items-start gap-2">
        <h3 class="flex-1 text-base font-semibold text-text-primary leading-snug">
          {solution.solution_name}
          {#if isNew}
            <span class="new-badge" aria-hidden="true">New</span>
            <span class="sr-only">Newly generated solution</span>
          {/if}
        </h3>
        <!-- Selection checkbox -->
        <button
          type="button"
          class="shrink-0 w-6 h-6 p-0.5 flex items-center justify-center rounded-full transition-colors
            {isToggleable ? 'hover:bg-accent/10' : ''}"
          onclick={handleCheckboxClick}
          aria-label={isSelected ? 'Deselect solution' : 'Select solution'}
          tabindex={-1}
        >
          {#if isSelected}
            <CheckCircle class="w-5 h-5 text-accent" />
          {:else if isToggleable}
            <Circle class="w-5 h-5 text-text-muted" />
          {:else}
            <Circle class="w-5 h-5 text-text-muted/40" />
          {/if}
        </button>
      </div>

      <!-- Badges row -->
      <div class="flex items-center gap-2 mt-1.5 flex-wrap">
        <Badge variant={superpower.variant} size="sm">{superpower.label}</Badge>
        {#if solution.project_type}
          <span class="text-xs px-2 py-0.5 rounded-full bg-bg-elevated border border-border text-text-muted">
            {solution.project_type}
          </span>
        {/if}
      </div>

      <!-- Value proposition tagline -->
      {#if solution.value_proposition}
        <p class="mt-2 text-xs italic text-text-muted truncate-3">
          {solution.value_proposition}
        </p>
      {/if}

      <!-- Description (clamped to 5 lines) -->
      <p class="mt-2 text-sm text-text-secondary leading-relaxed truncate-5">
        {solution.description}
      </p>

      <!-- Hover affordance -->
      <span class="mt-auto pt-2 inline-flex items-center gap-1 text-xs text-text-muted opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity">
        View details <ArrowRight class="w-3 h-3" />
      </span>
    </div>
  </div>
</div>

<style>
  .compact-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08), 0 1px 0 var(--color-accent);
  }

  /* Selected: accent tint + ring */
  .card-selected {
    background: color-mix(in srgb, var(--color-accent) 4%, var(--color-bg-card));
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--color-accent) 20%, transparent);
  }

  /* Selection pulse micro-interaction */
  :global(.selection-pulse) {
    animation: selectionPulse 300ms ease-out;
  }

  @keyframes selectionPulse {
    0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(229, 90, 40, 0); }
    50% { transform: scale(1.015); box-shadow: 0 0 0 4px rgba(229, 90, 40, 0.15); }
    100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(229, 90, 40, 0); }
  }

  .new-badge {
    font-size: 0.625rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 0.125rem 0.375rem;
    vertical-align: middle;
    margin-left: 0.25rem;
    border-radius: 9999px;
    color: var(--color-info);
    background: rgba(59, 130, 246, 0.1);
    border: 1px solid rgba(59, 130, 246, 0.2);
    animation: newBadgeFade 8s ease-out forwards;
  }

  @keyframes newBadgeFade {
    0%, 70% { opacity: 1; }
    100% { opacity: 0; }
  }

  @media (prefers-reduced-motion: reduce) {
    .new-badge {
      animation: none;
    }
  }
</style>
