<script lang="ts">
  import type { Snippet } from "svelte";
  import { ArrowRight, Heart } from "lucide-svelte";
  import { fly } from "svelte/transition";
  import Badge from "$lib/components/ui/Badge.svelte";
  import CategoryBadge from "$lib/components/catalog/CategoryBadge.svelte";
  import Tooltip from "$lib/components/ui/Tooltip.svelte";
  import { SCORE_DEFINITIONS } from "$lib/utils/scoreDefinitions";
  import { scoreRationale } from "$lib/utils/scoreRationale";
  import type { SolutionPreview } from "$lib/types/job";
  import {
    displayCompositeScore,
    solutionStrengthBadge,
    solutionPrimaryStrengthKey,
    solutionDisplayTitle,
    solutionCardDescription,
    fitLabel,
  } from "$lib/utils/solution-utils";
  import { tagDescription } from "$lib/utils/ideaTagLabels";
  import { angleLabel, angleDescription } from "$lib/utils/ideaAngleLabels";

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

  $effect(() => {
    if (import.meta.env.DEV && href && onSelect) {
      console.warn("SolutionCard: href and onSelect are mutually exclusive. Use one mode at a time.");
    }
  });

  const compositeScore = $derived(displayCompositeScore(solution));
  const compositeWhy = $derived(scoreRationale(solution, "composite"));
  const superpower = $derived(solutionStrengthBadge(solution));
  const strengthWhy = $derived(tagDescription(solutionPrimaryStrengthKey(solution)));
  const displayTitle = $derived(solutionDisplayTitle(solution));
  const cardDesc = $derived(solutionCardDescription(solution));
  const fit = $derived(fitLabel(solution.market_fit_score));

  const whyShort = $derived(solution.why_it_works_short?.trim() || null);
  const whyFallback = $derived(
    !whyShort && solution.why_it_works?.trim() ? solution.why_it_works.trim() : null,
  );

  const provenance = $derived.by(() => {
    const pain = solution.source_pain?.trim() || solution.pain_points_addressed?.[0]?.trim();
    if (!pain) return null;
    const seg = solution.source_segment?.trim();
    return seg ? `Generated for ${pain} - ${seg} audience` : `Addresses ${pain}`;
  });

  const scoreColor = $derived.by(() => {
    if (compositeScore === null) return "var(--color-text-muted)";
    if (compositeScore >= 0.7) return "var(--color-success)";
    if (compositeScore >= 0.4) return "var(--color-warning)";
    return "var(--color-error)";
  });

  let justSelected = $state(false);
  const isToggleable = $derived(!!onSelect && !disabled && (isSelected || !maxReached));

  function handleCardClick(e: MouseEvent) {
    if (href) {
      onclick?.(e);
      return;
    }
    onOpen?.();
  }

  let pulseTimer: ReturnType<typeof setTimeout> | null = null;
  $effect(() => {
    return () => { if (pulseTimer) clearTimeout(pulseTimer); };
  });

  function handleCheckboxChange(e: Event) {
    const target = e.currentTarget as HTMLInputElement;
    if (!onSelect) return;
    if (target.checked && !isSelected) {
      justSelected = true;
      if (pulseTimer) clearTimeout(pulseTimer);
      pulseTimer = setTimeout(() => { justSelected = false; pulseTimer = null; }, 300);
    }
    onSelect(solution.solution_name);
  }

  function handleDetailsClick(e: MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    onOpen?.();
  }
</script>

{#snippet scoreMetric()}
  {#if compositeWhy}
    <Tooltip content={compositeWhy} position="bottom" class="cursor-help">
      {#snippet children()}
        <span class="score-metric">
          <span>Score</span>
          <strong
            style:color={scoreColor}
            aria-label={compositeScore === null ? "Not scored" : undefined}
          >{compositeScore === null ? "--" : Math.round(compositeScore * 100)}</strong>
        </span>
      {/snippet}
    </Tooltip>
  {:else}
    <span class="score-metric">
      <span>Score</span>
      <strong
        style:color={scoreColor}
        aria-label={compositeScore === null ? "Not scored" : undefined}
      >{compositeScore === null ? "--" : Math.round(compositeScore * 100)}</strong>
    </span>
  {/if}
{/snippet}

{#snippet cardContent()}
  <div class="solution-card__head">
    <div class="solution-card__title-group">
      <div class="solution-card__badges">
        {#if isTopPick}<span class="top-pick-badge">Highest viability</span>{/if}
        {#if isNew}
          <span class="new-badge" aria-hidden="true">New</span>
          <span class="sr-only">Newly generated solution</span>
        {/if}
        {#if isFeatured}<Badge variant="accent" size="sm">Featured</Badge>{/if}
      </div>
      <h3>{displayTitle}</h3>
    </div>

    {#if onSelect}
      <span
        class="selection-indicator
          {isSelected ? 'selection-indicator--selected' : ''}
          {isToggleable && !isSelected ? 'selection-indicator--available' : ''}
          {!isToggleable && !isSelected ? 'selection-indicator--disabled' : ''}"
        aria-hidden="true"
      >
        {#if isSelected && selectionIndex}<span>{selectionIndex}</span>{/if}
      </span>
    {:else if actionSlot}
      <div class="solution-card__action-slot">{@render actionSlot()}</div>
    {/if}
  </div>

  <div class="solution-card__metrics">
    {@render scoreMetric()}
    {#if solution.market_fit_score != null}
      <Tooltip content={SCORE_DEFINITIONS.market_fit} position="bottom" class="cursor-help">
        {#snippet children()}
          <span class="mini-metric">
            <span>Fit</span>
            <strong class="fit-num fit-num-{fit.variant}">{Math.round((solution.market_fit_score ?? 0) * 100)}%</strong>
          </span>
        {/snippet}
      </Tooltip>
    {/if}
    {#if solution.estimated_development_time}
      <span class="mini-metric">
        <span>Build</span>
        <strong>~{solution.estimated_development_time}</strong>
      </span>
    {/if}
    {#if voteCount > 0 && !actionSlot}
      <span class="vote-mark" title="{voteCount} community vote{voteCount === 1 ? '' : 's'}">
        <Heart class="w-3 h-3" fill="currentColor" aria-hidden="true" />
        <span>{voteCount}</span>
      </span>
    {/if}
  </div>

  <div class="solution-card__tags">
    {#if superpower}
      {#if strengthWhy}
        <Tooltip content={strengthWhy} position="bottom" class="cursor-help">
          {#snippet children()}<span class="superpower-tag superpower-tag-{superpower.variant}">{superpower.label}</span>{/snippet}
        </Tooltip>
      {:else}
        <span class="superpower-tag superpower-tag-{superpower.variant}">{superpower.label}</span>
      {/if}
    {/if}
    {#if solution.winning_angle && angleLabel(solution.winning_angle)}
      <Tooltip content={solution.angle_rationale || angleDescription(solution.winning_angle)} position="bottom" class="cursor-help">
        {#snippet children()}<span class="angle-tag">{angleLabel(solution.winning_angle)}</span>{/snippet}
      </Tooltip>
    {/if}
    {#if solution.project_type}<span class="project-tag">{solution.project_type}</span>{/if}
  </div>

  <p class="solution-card__desc">{cardDesc}</p>

  {#if whyShort}
    <p class="solution-card__evidence">{whyShort}</p>
  {:else if whyFallback}
    <p class="solution-card__evidence truncate-1">{whyFallback}</p>
  {/if}

  {#if provenance}
    <p class="solution-card__provenance">{provenance}</p>
  {/if}

  <div class="solution-card__footer">
    {#if category}<CategoryBadge {category} type="ideas" light asLink={false} />{/if}
    {#if onSelect && onOpen}
      <button type="button" class="card-detail-btn" onclick={handleDetailsClick} aria-label="View {displayTitle} details">
        View details <ArrowRight class="w-3.5 h-3.5" aria-hidden="true" />
      </button>
    {:else}
      <span class="card-detail-btn" aria-hidden="true">View details <ArrowRight class="w-3.5 h-3.5" /></span>
    {/if}
  </div>
{/snippet}

{#if href}
  <a
    {href}
    onclick={handleCardClick}
    class="card card-interactive card-sm group solution-card solution-card-link {isTopPick ? 'is-top-pick' : ''}"
    in:fly={{ y: 12, duration: 300, delay: index * 35 }}
  >
    {@render cardContent()}
  </a>
{:else if onSelect}
  <label
    class="card group solution-card solution-card-select {isSelected ? 'card-selected' : ''} {justSelected ? 'selection-pulse' : ''} {isTopPick ? 'is-top-pick' : ''} {(disabled || maxReached) && !isSelected ? 'opacity-60' : ''}"
  >
    <input
      type="checkbox"
      class="sr-only peer"
      checked={isSelected}
      disabled={(disabled || (!isToggleable && !isSelected))}
      onchange={handleCheckboxChange}
      aria-label={isSelected ? `Deselect ${displayTitle}` : `Select ${displayTitle}`}
    />
    {@render cardContent()}
  </label>
{:else}
  <button
    type="button"
    class="card group solution-card solution-card-button {isTopPick ? 'is-top-pick' : ''}"
    onclick={handleCardClick}
    aria-label="Solution: {displayTitle}"
  >
    {@render cardContent()}
  </button>
{/if}

<style>
  .solution-card {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 0.625rem;
    min-height: 0;
    width: 100%;
    padding: 1rem;
    border-radius: var(--radius-md);
    text-align: left;
    overflow: hidden;
    transition: border-color 150ms ease, background-color 150ms ease, outline-color 150ms ease;
  }

  .solution-card:hover {
    border-color: var(--color-border-emphasis);
  }

  .solution-card-select {
    cursor: pointer;
  }

  .solution-card-button {
    cursor: pointer;
  }

  .solution-card.is-top-pick {
    border-color: color-mix(in srgb, var(--color-accent) 30%, var(--color-border));
  }

  .solution-card__head {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 0.75rem;
    align-items: start;
  }

  .solution-card__title-group {
    min-width: 0;
  }

  .solution-card__badges {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.375rem;
    min-height: 1.25rem;
    margin-bottom: 0.25rem;
  }

  .solution-card h3 {
    margin: 0;
    color: var(--color-text-primary);
    font-size: 0.9375rem;
    font-weight: 650;
    line-height: 1.3;
    text-wrap: pretty;
  }

  .top-pick-badge,
  .new-badge {
    display: inline-flex;
    align-items: center;
    min-height: 1.25rem;
    padding: 0.125rem 0.45rem;
    border-radius: 999px;
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    line-height: 1;
    text-transform: uppercase;
    white-space: nowrap;
  }

  .top-pick-badge {
    color: var(--color-accent-dark);
    background: var(--color-accent-subtle);
    border: 1px solid var(--color-border-accent);
  }

  .new-badge {
    color: var(--color-secondary-dark);
    background: var(--color-secondary-subtle);
    border: 1px solid rgba(99, 102, 241, 0.2);
  }

  .solution-card__metrics {
    display: flex;
    align-items: stretch;
    flex-wrap: wrap;
    gap: 0.5rem;
    min-width: 0;
  }

  .solution-card__metrics :global(.tooltip-wrapper) {
    display: flex;
    min-width: 0;
  }

  .score-metric,
  .mini-metric {
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 0.125rem;
    min-width: 4.75rem;
    min-height: 2.75rem;
    padding: 0.5rem 0.625rem;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    font-variant-numeric: tabular-nums;
  }

  .score-metric span,
  .mini-metric span {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  .score-metric strong {
    font-family: var(--font-display);
    font-size: 1.125rem;
    line-height: 1;
  }

  .mini-metric strong {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    font-weight: 700;
    color: var(--color-text-primary);
    line-height: 1.15;
  }

  .solution-card__tags {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.375rem;
    min-height: 1.4rem;
  }

  .superpower-tag,
  .angle-tag,
  .project-tag {
    display: inline-flex;
    align-items: center;
    min-height: 1.375rem;
    padding: 0.125rem 0.5rem;
    border-radius: 999px;
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 650;
    letter-spacing: 0.04em;
    line-height: 1.1;
    white-space: nowrap;
  }

  .superpower-tag {
    background: var(--color-bg-surface);
    border: 1px solid currentColor;
  }
  .superpower-tag-success { color: var(--color-success-dark); }
  .superpower-tag-accent { color: var(--color-accent-dark); }
  .superpower-tag-info { color: var(--color-secondary-dark); }
  .superpower-tag-warning { color: var(--color-warning-dark); }

  .angle-tag {
    background: var(--color-secondary-subtle);
    border: 1px solid rgba(99, 102, 241, 0.24);
    color: var(--color-secondary-dark);
  }

  .project-tag {
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    color: var(--color-text-muted);
  }

  .solution-card__desc {
    margin: 0;
    color: var(--color-text-secondary);
    font-size: 0.875rem;
    line-height: 1.5;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .solution-card__evidence {
    margin: 0;
    padding-left: 0.625rem;
    border-left: 2px solid var(--color-border-emphasis);
    color: var(--color-text-muted);
    font-size: 0.75rem;
    line-height: 1.45;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .solution-card__provenance {
    margin: 0;
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    line-height: 1.35;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .solution-card__desc,
  .solution-card__evidence,
  .solution-card__provenance {
    min-width: 0;
    max-width: 100%;
  }

  .solution-card__footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    margin-top: auto;
    padding-top: 0.25rem;
  }

  .card-detail-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    min-height: 2rem;
    padding: 0;
    margin-left: auto;
    background: transparent;
    border: none;
    color: var(--color-accent);
    font-size: 0.8125rem;
    font-weight: 650;
    white-space: nowrap;
    cursor: pointer;
  }

  .card-detail-btn:hover {
    text-decoration: underline;
    text-underline-offset: 3px;
  }

  .card-selected {
    background: color-mix(in srgb, var(--color-accent) 4%, var(--color-bg-elevated));
    outline: 2px solid color-mix(in srgb, var(--color-accent) 24%, transparent);
  }

  label.solution-card:has(input:focus-visible) {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  label.solution-card:has(input:disabled) {
    cursor: default;
  }

  :global(.selection-pulse) {
    animation: selectionPulse 260ms ease-out;
  }

  @keyframes selectionPulse {
    0% { transform: scale(1); }
    50% { transform: scale(1.01); }
    100% { transform: scale(1); }
  }

  .vote-mark {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.1875rem;
    min-height: 2.875rem;
    padding: 0 0.5rem;
    color: var(--color-accent);
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }

  .fit-num-success { color: var(--color-success-dark); }
  .fit-num-warning { color: var(--color-warning-dark); }
  .fit-num-muted { color: var(--color-text-muted); }

  .selection-indicator {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2rem;
    border-radius: 0.375rem;
    border: 2px solid var(--color-border-emphasis);
    background: var(--color-bg-elevated);
    color: white;
    font-family: var(--font-mono);
    font-size: 0.75rem;
    font-weight: 800;
    font-variant-numeric: tabular-nums;
    line-height: 1;
    transition: border-color 150ms ease, background 150ms ease, box-shadow 150ms ease, transform 120ms ease;
  }

  .selection-indicator::after {
    content: '';
    position: absolute;
    inset: -0.25rem;
  }

  .selection-indicator--available:hover {
    border-color: var(--color-accent);
    background: color-mix(in srgb, var(--color-accent) 8%, var(--color-bg-elevated));
  }

  .selection-indicator--selected {
    border-color: var(--color-accent);
    background: var(--color-accent);
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-accent) 15%, transparent);
  }

  .selection-indicator--disabled {
    border-color: var(--color-border);
    opacity: 0.45;
  }

  .selection-indicator:active:not(.selection-indicator--disabled) {
    transform: scale(0.94);
  }

  @media (max-width: 639px) {
    .solution-card {
      padding: 0.875rem;
    }

    .score-metric,
    .mini-metric {
      min-width: calc(50% - 0.25rem);
    }
  }
</style>
