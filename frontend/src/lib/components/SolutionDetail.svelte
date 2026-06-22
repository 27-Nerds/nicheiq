<script lang="ts">
  import type { Snippet } from "svelte";
  import {
    ChevronLeft,
    ChevronRight,
    X,
    Heart,
  } from "lucide-svelte";
  import { portal } from "$lib/actions/portal";
  import Badge from "$lib/components/ui/Badge.svelte";
  import ProgressRing from "$lib/components/ui/ProgressRing.svelte";
  import SolutionDetailContent from "$lib/components/SolutionDetailContent.svelte";
  import Tooltip from "$lib/components/ui/Tooltip.svelte";
  import { scoreRationale } from "$lib/utils/scoreRationale";
  import type { SolutionPreview } from "$lib/types/job";
  import { computeCompositeScore, getSuperpower, SUPERPOWER_MAP_DETAILED, solutionDisplayTitle, originalityMetric } from "$lib/utils/solution-utils";

  interface Props {
    open: boolean;
    solution: SolutionPreview;
    solutions: SolutionPreview[];
    currentIndex: number;
    isSelected?: boolean;
    disabled?: boolean;
    maxReached?: boolean;
    selectionIndex?: number;
    onSelect?: (name: string) => void;
    onNavigate: (index: number) => void;
    onClose: () => void;
    actionSlot?: Snippet;
    voteCount?: number;
  }

  let {
    open = $bindable(false),
    solution,
    solutions,
    currentIndex,
    isSelected = false,
    disabled = false,
    maxReached = false,
    selectionIndex = 0,
    onSelect,
    onNavigate,
    onClose,
    actionSlot,
    voteCount = 0,
  }: Props = $props();

  let modalEl: HTMLDivElement | undefined = $state();

  // Focus trap: focus modal when opened
  $effect(() => {
    if (open && modalEl) {
      modalEl.focus();
    }
  });

  const total = $derived(solutions.length);

  const compositeScore = $derived(computeCompositeScore(solution));

  // Score color (matches ProgressRing auto logic)
  const scoreColor = $derived.by(() => {
    if (compositeScore >= 0.7) return 'var(--color-success)';
    if (compositeScore >= 0.4) return 'var(--color-warning)';
    return 'var(--color-error)';
  });

  // Per-score color
  function individualScoreColor(value: number | null | undefined): string {
    if (value == null) return 'var(--color-text-muted)';
    if (value >= 0.7) return 'var(--color-success)';
    if (value >= 0.4) return 'var(--color-warning)';
    return 'var(--color-error)';
  }

  const origMetric = $derived(originalityMetric(solution));

  const individualScores = $derived([
    { label: "MF", value: solution.market_fit_score, why: scoreRationale(solution, "market_fit") },
    { label: "Feas", value: solution.technical_feasibility_score, why: scoreRationale(solution, "technical_feasibility") },
    { label: "SEO", value: solution.seo_scalability_score, why: scoreRationale(solution, "seo") },
    { label: origMetric.short ?? "Orig", value: origMetric.value, why: scoreRationale(solution, "novelty") },
    { label: "Solo", value: solution.solo_dev_feasibility, why: scoreRationale(solution, "solo_dev") },
  ]);

  const superpower = $derived(getSuperpower(solution, SUPERPOWER_MAP_DETAILED));

  const displayTitle = $derived(solutionDisplayTitle(solution));
  const hasHeadline = $derived(!!solution.headline?.trim());

  const isToggleable = $derived(!!onSelect && !disabled && (isSelected || !maxReached));

  function handleSelect() {
    if (!isToggleable || !onSelect) return;
    onSelect(solution.solution_name);
  }

  function navigatePrev() {
    const prev = currentIndex <= 0 ? total - 1 : currentIndex - 1;
    onNavigate(prev);
  }

  function navigateNext() {
    const next = currentIndex >= total - 1 ? 0 : currentIndex + 1;
    onNavigate(next);
  }

  function handleKeydown(e: KeyboardEvent) {
    if (!open) return;
    if (e.key === 'Escape') { onClose(); return; }
    if (e.key === 'ArrowLeft') { e.preventDefault(); navigatePrev(); }
    if (e.key === 'ArrowRight') { e.preventDefault(); navigateNext(); }
  }

  function handleBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget) {
      onClose();
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div
    use:portal
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur p-4"
    onclick={handleBackdropClick}
    role="dialog"
    aria-modal="true"
    aria-label="Solution details: {displayTitle}"
    tabindex="-1"
  >
    <!-- Nav arrow: Previous -->
    {#if total > 1}
      <button
        type="button"
        class="nav-arrow nav-arrow-left"
        onclick={navigatePrev}
        aria-label="Previous solution"
      >
        <ChevronLeft class="w-6 h-6" />
      </button>
    {/if}

    <!-- Modal card -->
    <div
      bind:this={modalEl}
      class="modal-card bg-bg-surface border border-border rounded-xl shadow-2xl w-full max-w-3xl max-h-[85vh] flex flex-col"
      tabindex="-1"
    >
      <!-- Header -->
      <div class="flex items-center justify-between gap-3 p-4 border-b border-border shrink-0">
        <div class="min-w-0">
          <h2 class="text-xl font-semibold text-text-primary line-clamp-2">{displayTitle}</h2>
          {#if hasHeadline}
            <p class="text-xs font-mono text-text-muted/60 mt-0.5">{solution.solution_name}</p>
          {/if}
          <div class="flex items-center gap-2 mt-1.5 flex-wrap">
            <div class="flex items-center gap-1">
              <ProgressRing value={compositeScore} size={24} showValue={false} color="auto" animate={false} showTooltip={false} flat={true} />
              <span class="text-sm font-semibold font-display" style:color={scoreColor}>{Math.round(compositeScore * 100)}</span>
            </div>
            {#if superpower}
              <Badge variant={superpower.variant} size="sm">{superpower.label}</Badge>
            {/if}
            {#if solution.project_type}
              <span class="text-xs px-2 py-0.5 rounded-full bg-bg-elevated border border-border text-text-muted">
                {solution.project_type}
              </span>
            {/if}
            {#if voteCount > 0}
              <span class="text-xs px-2 py-0.5 rounded-full bg-accent/8 border border-accent/20 text-accent flex items-center gap-1">
                <Heart class="w-3 h-3" /> {voteCount} vote{voteCount === 1 ? '' : 's'}
              </span>
            {/if}
            <!-- Individual score breakdown -->
            <span class="hidden sm:inline w-px h-3 bg-border-emphasis"></span>
            {#snippet scoreBadge(s: { label: string; value: number | null | undefined })}
              <span class="text-[10px] text-text-muted">
                {s.label}:<span class="font-semibold tabular-nums ml-0.5" style:color={individualScoreColor(s.value)}>{s.value != null ? (s.value * 100).toFixed(0) : '--'}</span>
              </span>
            {/snippet}
            {#each individualScores as s}
              <span class="hidden sm:inline-flex items-center">
                {#if s.why}
                  <Tooltip content={s.why} position="bottom" class="cursor-help">
                    {#snippet children()}{@render scoreBadge(s)}{/snippet}
                  </Tooltip>
                {:else}
                  {@render scoreBadge(s)}
                {/if}
              </span>
            {/each}
          </div>
        </div>
        <div class="flex items-center gap-2 shrink-0">
          {#if total > 1}
            <span class="hidden sm:inline text-xs text-text-muted tabular-nums">{currentIndex + 1} of {total}</span>
          {/if}
          {#if onSelect}
            <!-- Select / Deselect button (hidden on mobile — footer CTA handles it) -->
            <div class="hidden sm:flex">
              <button
                type="button"
                onclick={handleSelect}
                disabled={!isToggleable}
                title={maxReached && !isSelected ? 'Maximum 3 solutions selected' : undefined}
                class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors
                  {isSelected
                    ? 'bg-accent/10 text-accent border border-accent/30 hover:bg-accent/15'
                    : 'bg-bg-elevated text-text-secondary border border-border hover:border-accent/40 hover:text-accent'
                  }
                  disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <span class="inline-flex items-center justify-center w-5 h-5 rounded-md text-xs font-bold tabular-nums
                  {isSelected ? 'bg-accent text-white' : 'border-2 border-current'}">
                  {#if isSelected && selectionIndex}{selectionIndex}{/if}
                </span>
                {#if isSelected}
                  Selected
                {:else if maxReached}
                  Limit reached
                {:else}
                  Select
                {/if}
              </button>
            </div>
          {:else if actionSlot}
            {@render actionSlot()}
          {/if}
          <!-- Close button -->
          <button
            type="button"
            onclick={onClose}
            aria-label="Close details"
            class="p-1.5 rounded-lg hover:bg-bg-hover text-text-muted hover:text-text-primary transition-colors"
          >
            <X class="w-5 h-5" />
          </button>
        </div>
      </div>

      <!-- Scrollable body -->
      <div class="p-5 overflow-y-auto flex-1">
        <SolutionDetailContent {solution} />
      </div>

      <!-- Sticky footer select CTA -->
      {#if onSelect}
        <div class="shrink-0 border-t border-border p-3">
          <button
            type="button"
            onclick={handleSelect}
            disabled={!isToggleable}
            title={maxReached && !isSelected ? 'Maximum 3 solutions selected' : undefined}
            class="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors
              {isSelected
                ? 'bg-accent/10 text-accent border border-accent/30 hover:bg-accent/15'
                : 'btn-primary'
              }
              disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <span class="inline-flex items-center justify-center w-5 h-5 rounded-md text-xs font-bold tabular-nums
              {isSelected ? 'bg-accent text-white' : 'border-2 border-current'}">
              {#if isSelected && selectionIndex}{selectionIndex}{/if}
            </span>
            {#if isSelected}
              Selected
            {:else if maxReached}
              Limit reached
            {:else}
              Select this idea
            {/if}
          </button>
        </div>
      {/if}
    </div>

    <!-- Nav arrow: Next -->
    {#if total > 1}
      <button
        type="button"
        class="nav-arrow nav-arrow-right"
        onclick={navigateNext}
        aria-label="Next solution"
      >
        <ChevronRight class="w-6 h-6" />
      </button>
    {/if}
  </div>
{/if}

<style>
  .modal-card {
    position: relative;
    z-index: 1;
  }

  .nav-arrow {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    z-index: 2;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 48px;
    height: 48px;
    border-radius: 50%;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    color: var(--color-text-secondary);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .nav-arrow:hover {
    background: var(--color-bg-elevated);
    color: var(--color-text-primary);
    border-color: var(--color-accent);
  }

  .nav-arrow-left {
    left: max(0.5rem, calc(50% - 28rem));
  }

  .nav-arrow-right {
    right: max(0.5rem, calc(50% - 28rem));
  }

  /* On smaller screens, position arrows at edge */
  @media (max-width: 900px) {
    .nav-arrow-left {
      left: 0.25rem;
    }
    .nav-arrow-right {
      right: 0.25rem;
    }
  }

  /* Hide arrows on very small screens (use keyboard/swipe instead) */
  @media (max-width: 480px) {
    .nav-arrow {
      display: none;
    }
  }
</style>
