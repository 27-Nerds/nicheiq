<script lang="ts">
  import type { Snippet } from "svelte";
  import {
    CheckCircle,
    Circle,
    ArrowRight,
    Heart,
  } from "lucide-svelte";
  import ProgressRing from "$lib/components/ui/ProgressRing.svelte";
  import type { SolutionPreview } from "$lib/types/job";
  import { computeCompositeScore, getSuperpower, SUPERPOWER_MAP } from "$lib/utils/solution-utils";

  interface Props {
    solution: SolutionPreview;
    onSelect?: (name: string) => void;
    onOpen: () => void;
    disabled?: boolean;
    isSelected?: boolean;
    maxReached?: boolean;
    isNew?: boolean;
    actionSlot?: Snippet;
    voteCount?: number;
  }

  let {
    solution,
    onSelect,
    onOpen,
    disabled = false,
    isSelected = false,
    maxReached = false,
    isNew = false,
    actionSlot,
    voteCount = 0,
  }: Props = $props();

  const compositeScore = $derived(computeCompositeScore(solution));
  const superpower = $derived(getSuperpower(solution, SUPERPOWER_MAP));

  // Selection pulse micro-interaction
  let justSelected = $state(false);

  // Card is selectable (checkbox toggle)
  const isToggleable = $derived(!!onSelect && !disabled && (isSelected || !maxReached));

  function handleCardClick() {
    onOpen();
  }

  function handleCheckboxClick(e: MouseEvent) {
    e.stopPropagation();
    if (!isToggleable || !onSelect) return;
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

<div
  class="card compact-card group p-3 relative transition-all duration-200 cursor-pointer
    {isSelected ? 'card-selected' : ''}
    {justSelected ? 'selection-pulse' : ''}
    {(disabled || maxReached) && !isSelected ? 'opacity-60 cursor-default' : ''}"
  role="button"
  aria-pressed={onSelect ? isSelected : undefined}
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
      <!-- Title + Checkbox / Action slot -->
      <div class="flex items-start gap-2">
        <h3 class="flex-1 min-w-0 text-base font-semibold text-text-primary leading-snug break-words">
          {solution.solution_name}
          {#if isNew}
            <span class="new-badge" aria-hidden="true">New</span>
            <span class="sr-only">Newly generated solution</span>
          {/if}
        </h3>
        {#if onSelect}
          <!-- Selection checkbox -->
          <button
            type="button"
            class="shrink-0 w-6 h-6 p-0.5 flex items-center justify-center rounded-full transition-colors
              {isToggleable ? 'hover:bg-accent/10' : ''}"
            onclick={handleCheckboxClick}
            aria-label={isSelected ? 'Deselect solution' : 'Select solution'}
            title={maxReached && !isSelected ? 'Maximum 3 solutions selected' : undefined}
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
        {:else if actionSlot}
          <div class="shrink-0">
            {@render actionSlot()}
          </div>
        {/if}
      </div>

      <!-- Badges row -->
      <div class="flex items-center gap-2 mt-1.5 flex-wrap">
        {#if superpower}
          <span class="superpower-tag superpower-tag-{superpower.variant}">{superpower.label}</span>
        {/if}
        {#if solution.project_type}
          <span class="text-xs px-2 py-0.5 rounded-full bg-bg-elevated border border-border text-text-muted">
            {solution.project_type}
          </span>
        {/if}
        {#if voteCount > 0}
          <span class="text-xs px-2 py-0.5 rounded-full bg-accent/8 border border-accent/20 text-accent flex items-center gap-1">
            <Heart class="w-3 h-3" /> {voteCount}
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
    border-bottom: 1px solid var(--color-accent);
  }

  /* Selected: accent tint + ring */
  .card-selected {
    background: color-mix(in srgb, var(--color-accent) 4%, var(--color-bg-card));
    outline: 2px solid color-mix(in srgb, var(--color-accent) 20%, transparent);
  }

  /* Selection pulse micro-interaction */
  :global(.selection-pulse) {
    animation: selectionPulse 300ms ease-out;
  }

  @keyframes selectionPulse {
    0% { transform: scale(1); }
    50% { transform: scale(1.015); }
    100% { transform: scale(1); }
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
