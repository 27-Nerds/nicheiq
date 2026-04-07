<script lang="ts">
  import type { Snippet } from "svelte";
  import {
    ArrowRight,
    Heart,
  } from "lucide-svelte";
  import { fly } from "svelte/transition";
  import Badge from "$lib/components/ui/Badge.svelte";
  import CategoryBadge from "$lib/components/catalog/CategoryBadge.svelte";
  import type { SolutionPreview } from "$lib/types/job";
  import { computeCompositeScore, getSuperpower, SUPERPOWER_MAP, solutionDisplayTitle, solutionCardDescription, fitLabel } from "$lib/utils/solution-utils";

  interface Props {
    solution: SolutionPreview;
    /** Opens detail modal (button/readonly mode) */
    onOpen?: () => void;
    /** Enables checkbox selection mode */
    onSelect?: (name: string) => void;
    disabled?: boolean;
    isSelected?: boolean;
    maxReached?: boolean;
    isNew?: boolean;
    isTopPick?: boolean;
    selectionIndex?: number;
    voteCount?: number;
    /** Custom action snippet (e.g. vote button in shared view) */
    actionSlot?: Snippet;
    /** Link mode: render as <a> with fly transition */
    href?: string;
    /** Click handler for link mode */
    onclick?: (e: MouseEvent) => void;
    /** Fly-in animation delay index */
    index?: number;
    /** Show "Featured" badge */
    isFeatured?: boolean;
    /** Show category badge */
    category?: { slug: string; name: string } | null;
  }

  let {
    solution,
    onOpen,
    onSelect,
    disabled = false,
    isSelected = false,
    maxReached = false,
    isNew = false,
    isTopPick = false,
    selectionIndex = 0,
    voteCount = 0,
    actionSlot,
    href,
    onclick,
    index = 0,
    isFeatured = false,
    category = null,
  }: Props = $props();

  // Dev guard: mixed-mode usage
  $effect(() => {
    if (import.meta.env.DEV && href && onSelect) {
      console.warn('SolutionCard: href and onSelect are mutually exclusive. Use one mode at a time.');
    }
  });

  // Mode
  const variant = $derived<'selection' | 'link' | 'readonly'>(
    onSelect ? 'selection' : href ? 'link' : 'readonly'
  );

  // Derived display data
  const compositeScore = $derived(computeCompositeScore(solution));
  const superpower = $derived(getSuperpower(solution, SUPERPOWER_MAP));
  const displayTitle = $derived(solutionDisplayTitle(solution));
  const cardDesc = $derived(solutionCardDescription(solution));
  const hasHeadline = $derived(!!solution.headline?.trim());
  const fit = $derived(fitLabel(solution.market_fit_score));

  // why_it_works_short with fallback
  const whyShort = $derived(
    solution.why_it_works_short?.trim() || null
  );
  const whyFallback = $derived(
    !whyShort && solution.why_it_works?.trim() ? solution.why_it_works.trim() : null
  );

  // Score color
  const scoreColor = $derived.by(() => {
    if (compositeScore >= 0.7) return 'var(--color-success)';
    if (compositeScore >= 0.4) return 'var(--color-warning)';
    return 'var(--color-error)';
  });

  // Selection pulse micro-interaction
  let justSelected = $state(false);

  // Card is selectable (checkbox toggle)
  const isToggleable = $derived(!!onSelect && !disabled && (isSelected || !maxReached));

  function handleCardClick(e: MouseEvent) {
    if (href) {
      onclick?.(e);
      return;
    }
    onOpen?.();
  }

  // Clear pulse timer on unmount
  let pulseTimer: ReturnType<typeof setTimeout> | null = null;
  $effect(() => {
    return () => { if (pulseTimer) clearTimeout(pulseTimer); };
  });

  function handleCheckboxClick(e: MouseEvent) {
    e.stopPropagation();
    if (!isToggleable || !onSelect) return;
    if (!isSelected) {
      justSelected = true;
      if (pulseTimer) clearTimeout(pulseTimer);
      pulseTimer = setTimeout(() => { justSelected = false; pulseTimer = null; }, 300);
    }
    onSelect(solution.solution_name);
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      // Space toggles selection when in selection mode, Enter opens detail
      if (e.key === ' ' && isToggleable && onSelect) {
        if (!isSelected) {
          justSelected = true;
          if (pulseTimer) clearTimeout(pulseTimer);
          pulseTimer = setTimeout(() => { justSelected = false; pulseTimer = null; }, 300);
        }
        onSelect(solution.solution_name);
      } else {
        onOpen?.();
      }
    }
  }
</script>

{#snippet cardContent()}
  {#if isTopPick}
    <span class="absolute -top-2.5 right-3 z-10 text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-full
      text-accent border border-accent/30 whitespace-nowrap shadow-sm"
      style="background-color: var(--color-bg-elevated)">
      Highest viability
    </span>
  {/if}

  <!-- Title + Checkbox / Action slot -->
  <div class="flex items-start gap-2">
    <h3 class="flex-1 min-w-0 text-sm font-semibold text-text-primary leading-snug break-words truncate-2 group-hover:text-accent transition-colors">
      {displayTitle}
      {#if isNew}
        <span class="new-badge" aria-hidden="true">New</span>
        <span class="sr-only">Newly generated solution</span>
      {/if}
      {#if isFeatured}
        <Badge variant="accent" size="sm">Featured</Badge>
      {/if}
    </h3>
    {#if onSelect}
      <!-- Selection checkbox (numbered square) -->
      <button
        type="button"
        class="selection-indicator shrink-0 w-6 h-6 flex items-center justify-center transition-all
          {isSelected ? 'selection-indicator--selected' : ''}
          {isToggleable && !isSelected ? 'selection-indicator--available' : ''}
          {!isToggleable && !isSelected ? 'selection-indicator--disabled' : ''}"
        onclick={handleCheckboxClick}
        role="checkbox"
        aria-checked={isSelected}
        aria-label={isSelected ? `Deselect solution (selection ${selectionIndex})` : 'Select solution'}
        title={maxReached && !isSelected ? 'Maximum 3 solutions selected' : undefined}
        tabindex={-1}
      >
        {#if isSelected && selectionIndex}
          <span class="selection-indicator__number">{selectionIndex}</span>
        {/if}
      </button>
    {:else if actionSlot}
      <div class="shrink-0">
        {@render actionSlot()}
      </div>
    {/if}
  </div>

  <!-- Metrics row -->
  <div class="flex items-center gap-2 mt-1.5 flex-wrap">
    <span class="text-sm font-bold font-display tabular-nums" style:color={scoreColor}>{Math.round(compositeScore * 100)}</span>
    {#if fit.text}
      <span class="fit-label fit-label-{fit.variant}">{fit.text}</span>
    {/if}
    {#if superpower}
      <span class="superpower-tag superpower-tag-{superpower.variant}">{superpower.label}</span>
    {/if}
    {#if solution.project_type}
      <span class="text-xs px-2 py-0.5 rounded-full bg-bg-elevated border border-border text-text-muted">
        {solution.project_type}
      </span>
    {/if}
    {#if solution.estimated_development_time}
      <span class="text-xs font-mono text-text-muted tabular-nums">
        ~{solution.estimated_development_time}
      </span>
    {/if}
    {#if voteCount > 0}
      <span class="text-xs px-2 py-0.5 rounded-full bg-accent/8 border border-accent/20 text-accent flex items-center gap-1">
        <Heart class="w-3 h-3" /> {voteCount}
      </span>
    {/if}
    {#if hasHeadline}
      <span class="ml-auto text-[10px] font-mono text-text-muted/60 truncate max-w-[120px]">{solution.solution_name}</span>
    {/if}
  </div>

  <!-- Description -->
  <p class="mt-2 text-sm text-text-secondary leading-relaxed truncate-3">
    {cardDesc}
  </p>

  <!-- Why it works callout -->
  {#if whyShort}
    <p class="mt-1.5 text-xs text-text-muted leading-relaxed pl-2 border-l-2 border-border-emphasis">
      &#x21B3; {whyShort}
    </p>
  {:else if whyFallback}
    <p class="mt-1.5 text-xs text-text-muted leading-relaxed truncate-1 pl-2 border-l-2 border-border-emphasis">
      &#x21B3; {whyFallback}
    </p>
  {/if}

  <!-- Category badge -->
  {#if category}
    <div class="mt-1.5">
      <CategoryBadge {category} type="ideas" light asLink={false} />
    </div>
  {/if}

  <!-- Hover affordance -->
  <span class="mt-auto pt-2 inline-flex items-center gap-1 text-xs text-text-muted opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity">
    View details <ArrowRight class="w-3 h-3" />
  </span>
{/snippet}

<!-- Link mode: <a> with fly transition -->
{#if href}
  <a
    {href}
    onclick={handleCardClick}
    class="block w-full text-left card card-interactive card-sm group solution-card overflow-visible
      {isTopPick ? 'relative mt-3' : ''}"
    in:fly={{ y: 12, duration: 400, delay: index * 40 }}
  >
    {@render cardContent()}
  </a>
<!-- Button/selection mode: <div> -->
{:else}
  <div
    class="card solution-card group p-3 relative transition-all duration-200 cursor-pointer overflow-visible
      {isSelected ? 'card-selected' : ''}
      {justSelected ? 'selection-pulse' : ''}
      {isTopPick ? 'border-border-emphasis mt-3' : ''}
      {(disabled || maxReached) && !isSelected ? 'opacity-60 cursor-default' : ''}"
    role="button"
    aria-pressed={onSelect ? isSelected : undefined}
    aria-label="Solution: {displayTitle}"
    tabindex={0}
    onclick={handleCardClick}
    onkeydown={handleKeydown}
  >
    {@render cardContent()}
  </div>
{/if}

<style>
  .solution-card:hover {
    border-color: var(--color-border-emphasis);
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

  .fit-label {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 0.125rem 0.375rem;
    border-radius: 0.25rem;
  }
  .fit-label-success {
    color: var(--color-success-dark);
    background: rgba(34, 197, 94, 0.1);
  }
  .fit-label-warning {
    color: var(--color-warning-dark);
    background: rgba(234, 179, 8, 0.1);
  }
  .fit-label-muted {
    color: var(--color-text-muted);
    background: var(--color-bg-elevated);
  }

  /* --- Selection indicator (numbered checkbox) --- */
  .selection-indicator {
    position: relative;
    border-radius: 0.375rem;
    border: 2px solid var(--color-border-emphasis);
    background: transparent;
    cursor: pointer;
    font-size: 0.75rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    line-height: 1;
    padding: 0;
    transition: border-color 150ms ease, background 150ms ease,
                box-shadow 150ms ease, transform 120ms ease;
  }

  /* Expanded hit area (visual 24px, tap target 32px) */
  .selection-indicator::after {
    content: '';
    position: absolute;
    inset: -4px;
  }

  .selection-indicator--available:hover {
    border-color: var(--color-accent);
    background: color-mix(in srgb, var(--color-accent) 8%, transparent);
  }

  .selection-indicator--selected {
    border-color: var(--color-accent);
    background: var(--color-accent);
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-accent) 15%, transparent);
  }

  .selection-indicator__number {
    color: white;
    display: block;
    animation: indicator-pop 200ms cubic-bezier(0.34, 1.56, 0.64, 1);
  }

  @keyframes indicator-pop {
    0%   { transform: scale(0); opacity: 0; }
    100% { transform: scale(1); opacity: 1; }
  }

  .selection-indicator--disabled {
    border-color: var(--color-border);
    opacity: 0.4;
    cursor: default;
  }

  .selection-indicator:active:not(.selection-indicator--disabled) {
    transform: scale(0.9);
  }
</style>
