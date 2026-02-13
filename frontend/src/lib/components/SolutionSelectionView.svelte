<script lang="ts">
  import {
    Loader2,
    Sparkles,
    Lightbulb,
    AlertCircle,
    ArrowRight,
  } from "lucide-svelte";
  import SolutionCard from "./SolutionCard.svelte";
  import SolutionDetail from "./SolutionDetail.svelte";
  import SelectSolutionModal from "./SelectSolutionModal.svelte";
  import AnimateOnScroll from "$lib/components/ui/AnimateOnScroll.svelte";
  import type { SolutionPreview } from "$lib/types/job";
  import { selectSolution, regenerateIdeas } from "$lib/api";

  const MAX_SELECTIONS = 3;

  interface Props {
    jobId: string;
    solutions: SolutionPreview[];
    selectedSolution?: string | null;
    selectedSolutions?: string[] | null;
    isRegenerating?: boolean;
    canRegenerate?: boolean;
    onSelectionComplete?: () => void;
    onRegenerateStart?: () => void;
  }

  let {
    jobId,
    solutions = $bindable(),
    selectedSolution = null,
    selectedSolutions = null,
    isRegenerating = false,
    canRegenerate = true,
    onSelectionComplete,
    onRegenerateStart,
  }: Props = $props();

  // Track user's multi-select choices (before confirmation)
  let selectedNames = $state<Set<string>>(new Set());
  let modalOpen = $state(false);
  let selectLoading = $state(false);
  let selectError = $state("");
  let regenerating = $state(false);
  let regenerateError = $state("");

  // Horizon expander: track original batch for divider + badges
  let originalBatchSize = $state(solutions.length);
  let initialLoadDone = $state(solutions.length > 0);
  let hasRevealedNewBatch = $state(false);
  let showNewBadges = $state(false);
  let wasRegenerating = $state(false);

  // Detect when new ideas arrive via SSE
  $effect(() => {
    if (!initialLoadDone && solutions.length > 0) {
      // First load (solutions went from 0 to N) — this is the original batch, not a new one
      initialLoadDone = true;
      originalBatchSize = solutions.length;
      return;
    }

    if (initialLoadDone && solutions.length > originalBatchSize && !hasRevealedNewBatch) {
      hasRevealedNewBatch = true;
      showNewBadges = true;

      // Auto-scroll to divider if not already visible
      setTimeout(() => {
        const el = document.getElementById('batch-divider');
        if (!el) return;
        const rect = el.getBoundingClientRect();
        if (rect.top < 0 || rect.bottom > window.innerHeight) {
          const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
          el.scrollIntoView({
            behavior: prefersReducedMotion ? 'instant' : 'smooth',
            block: 'center',
          });
        }
      }, 400);

      // Remove "New" badges after 8s
      setTimeout(() => { showNewBadges = false; }, 8000);
    }
  });

  // Detect regeneration failure via SSE state transitions
  $effect(() => {
    if (isRegenerating) {
      // SSE confirms backend is regenerating — hand off from local state
      regenerating = false;
      wasRegenerating = true;
    } else if (wasRegenerating) {
      // isRegenerating just went false. Was it success or failure?
      wasRegenerating = false;
      // canRegenerate === true means backend reverted ideasRegeneratedAt to null (failure)
      // canRegenerate === false means ideasRegeneratedAt stayed set (success)
      if (canRegenerate) {
        regenerateError = 'Couldn\'t generate new ideas — this sometimes happens with niche-specific data. You can try again.';
      }
    }
  });

  // Modal detail state
  let modalIndex = $state<number | null>(null);

  // Whether selection has already been submitted (from DB)
  const alreadySubmitted = $derived(
    !!(selectedSolution || (selectedSolutions && selectedSolutions.length > 0))
  );

  // The set of names already submitted (for display)
  const submittedNames = $derived<Set<string>>(
    new Set(selectedSolutions ?? (selectedSolution ? [selectedSolution] : []))
  );

  const selectionCount = $derived(selectedNames.size);
  const canSubmit = $derived(selectionCount > 0 && !alreadySubmitted);

  // Dynamic header narrative based on selection count
  const headerNarrative = $derived.by(() => {
    if (alreadySubmitted) return { title: `Solution${submittedNames.size > 1 ? 's' : ''} Selected`, subtitle: '' };
    if (isRegenerating) return { title: 'Generating New Solutions...', subtitle: 'New solutions are being generated and will be added to your options shortly.' };
    switch (selectionCount) {
      case 0: return { title: 'Choose Your Solutions', subtitle: `Pick up to ${MAX_SELECTIONS} solutions. We'll analyze all of them, feature the strongest in your report, and include the rest as alternatives.` };
      case 1: return { title: 'Strong start', subtitle: `Add up to ${MAX_SELECTIONS - 1} more for broader coverage — the report will feature the strongest with the rest as alternatives.` };
      case 2: return { title: 'Two strong contenders', subtitle: 'Add a third to maximize coverage, or start now — we\'ll run a complete analysis either way.' };
      default: return { title: 'Maximum coverage', subtitle: `All ${MAX_SELECTIONS} slots filled. We'll evaluate market fit, feasibility, and SEO potential across all of them.` };
    }
  });

  function handleToggle(name: string) {
    if (alreadySubmitted || selectLoading || isRegenerating) return;

    const next = new Set(selectedNames);
    if (next.has(name)) {
      next.delete(name);
    } else if (next.size < MAX_SELECTIONS) {
      next.add(name);
    }
    selectedNames = next;
  }

  function handleOpenDetail(i: number) {
    modalIndex = i;
  }

  function handleNavigate(i: number) {
    modalIndex = i;
  }

  function handleCloseDetail() {
    modalIndex = null;
  }

  function handleSubmitClick() {
    if (!canSubmit) return;
    selectError = "";
    modalOpen = true;
  }

  async function handleConfirmSelection(rationale: string) {
    selectLoading = true;
    selectError = "";

    try {
      await selectSolution(jobId, {
        solutionNames: Array.from(selectedNames),
        rationale: rationale || undefined,
      });
      modalOpen = false;
      onSelectionComplete?.();
    } catch (e) {
      selectError =
        e instanceof Error ? e.message : "Failed to select solution";
    } finally {
      selectLoading = false;
    }
  }

  function handleCancelModal() {
    modalOpen = false;
    selectError = "";
  }

  async function handleRegenerate() {
    if (regenerating) return;
    regenerating = true;
    regenerateError = "";

    try {
      await regenerateIdeas(jobId);
      onRegenerateStart?.();
      // Keep regenerating=true — SSE will set isRegenerating, then new cards arrive and button disappears
    } catch (e) {
      regenerateError =
        e instanceof Error ? e.message : "Failed to regenerate ideas";
      regenerating = false;
    }
  }
</script>

<div class="space-y-6">
  <!-- Header -->
  <div class="card p-3">
    <div class="flex items-start gap-3">
      <div class="p-2 rounded-xl bg-accent/10 border border-accent/20 shrink-0">
        <Lightbulb class="w-4 h-4 text-accent" />
      </div>
      <div class="flex-1">
        <h2 class="text-lg font-semibold text-text-primary">
          {headerNarrative.title}
        </h2>
        <p class="mt-1 text-sm text-text-secondary">
          {#if alreadySubmitted}
            {#if submittedNames.size === 1}
              You selected <span class="font-medium text-text-primary">{[...submittedNames][0]}</span>. Deep analysis is in progress.
            {:else}
              You selected {submittedNames.size} solutions. The system is evaluating all of them and will feature the strongest in your report.
            {/if}
          {:else}
            {headerNarrative.subtitle}
          {/if}
        </p>
        {#if !alreadySubmitted && selectionCount > 0}
          <div class="flex flex-wrap items-center gap-1.5 mt-2">
            {#each [...selectedNames] as name}
              <span class="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-accent/8 border border-accent/20 text-accent font-medium">
                {name}
                <button
                  type="button"
                  class="ml-0.5 hover:text-accent-hover transition-colors"
                  aria-label="Remove {name}"
                  onclick={() => handleToggle(name)}
                >
                  &times;
                </button>
              </span>
            {/each}
          </div>
        {/if}
      </div>

      <!-- Selection counter + submit button -->
      {#if !alreadySubmitted && !isRegenerating}
        <div class="flex items-center gap-3 shrink-0">
          {#if selectionCount > 0}
            <span class="text-sm font-medium text-accent tabular-nums">
              {selectionCount}/{MAX_SELECTIONS}
            </span>
          {/if}
          <button
            onclick={handleSubmitClick}
            disabled={!canSubmit || selectLoading}
            class="btn-primary px-4 py-2 text-sm font-medium rounded-lg flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {#if selectLoading}
              <Loader2 class="w-4 h-4 animate-spin motion-reduce:animate-none" />
              Submitting...
            {:else}
              Run Deep Analysis
              <ArrowRight class="w-4 h-4" />
            {/if}
          </button>
        </div>
      {/if}
    </div>
  </div>

  <!-- Solution Cards Grid -->
  <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
    {#each solutions as solution, i}
      <!-- Batch divider before first new card -->
      {#if i === originalBatchSize && solutions.length > originalBatchSize}
        <div class="col-span-full">
          <AnimateOnScroll animation="fade-in" delay={100} duration={400} once={true}>
            <div id="batch-divider" class="flex items-center gap-3 py-2">
              <div class="flex-1 h-px bg-gradient-to-r from-transparent via-border-emphasis to-transparent"></div>
              <span class="text-xs font-mono font-medium uppercase tracking-wider text-text-muted whitespace-nowrap">
                Round 2 &middot; Fresh Perspectives
              </span>
              <div class="flex-1 h-px bg-gradient-to-r from-transparent via-border-emphasis to-transparent"></div>
            </div>
          </AnimateOnScroll>
        </div>
      {/if}

      <AnimateOnScroll
        animation={i >= originalBatchSize ? "scale-in" : "fade-up"}
        delay={i >= originalBatchSize
          ? 200 + (i - originalBatchSize) * 80
          : 80 + i * 80}
        duration={500}
        once={true}
      >
        <SolutionCard
          {solution}
          onSelect={handleToggle}
          onOpen={() => handleOpenDetail(i)}
          disabled={alreadySubmitted || selectLoading || isRegenerating}
          isSelected={alreadySubmitted
            ? submittedNames.has(solution.solution_name)
            : selectedNames.has(solution.solution_name)}
          maxReached={!alreadySubmitted && selectionCount >= MAX_SELECTIONS}
          isNew={showNewBadges && i >= originalBatchSize}
        />
      </AnimateOnScroll>
    {/each}

    <!-- Generate More card (last grid cell) -->
    {#if !alreadySubmitted && (canRegenerate || regenerating || isRegenerating)}
      <AnimateOnScroll animation="fade-up" delay={100 + Math.floor(solutions.length / 3) * 150} duration={500} once={true}>
        <button
          onclick={handleRegenerate}
          disabled={regenerating || isRegenerating}
          class="generate-more-card h-full w-full"
          class:is-loading={regenerating || isRegenerating}
          aria-label="Generate more solution ideas"
        >
          {#if regenerating || isRegenerating}
            <div class="p-2.5 rounded-xl bg-accent/10">
              <Loader2 class="w-5 h-5 text-accent animate-spin motion-reduce:animate-none" />
            </div>
            <span class="text-sm font-medium text-text-secondary mt-2.5">Exploring new angles...</span>
            <span class="text-xs text-text-muted mt-0.5">This may take a moment</span>
          {:else}
            <div class="p-2.5 rounded-xl bg-accent/10 group-icon">
              <Sparkles class="w-5 h-5 text-accent" />
            </div>
            <span class="text-sm font-semibold text-text-primary mt-2.5">Generate More Ideas</span>
            <span class="text-xs text-text-muted mt-0.5">One-time boost</span>
          {/if}
        </button>
      </AnimateOnScroll>
    {/if}

    <!-- Regeneration error (inside grid) -->
    {#if regenerateError}
      <div class="col-span-full flex items-center gap-2 p-3 bg-error/10 border border-error/20 rounded-lg text-error text-sm">
        <AlertCircle class="w-4 h-4 shrink-0" />
        <span>{regenerateError}</span>
      </div>
    {/if}
  </div>

  <!-- Screen reader announcement for new content -->
  <div class="sr-only" role="status" aria-live="polite">
    {#if solutions.length > originalBatchSize && hasRevealedNewBatch}
      {solutions.length - originalBatchSize} new solution ideas added below.
    {/if}
  </div>
</div>

<!-- Solution Detail Modal (outside main container so fixed positioning works) -->
{#if modalIndex !== null}
  <SolutionDetail
    open={modalIndex !== null}
    solution={solutions[modalIndex]}
    {solutions}
    currentIndex={modalIndex}
    isSelected={alreadySubmitted
      ? submittedNames.has(solutions[modalIndex].solution_name)
      : selectedNames.has(solutions[modalIndex].solution_name)}
    disabled={alreadySubmitted || selectLoading || isRegenerating}
    maxReached={!alreadySubmitted && selectionCount >= MAX_SELECTIONS}
    onSelect={handleToggle}
    onNavigate={handleNavigate}
    onClose={handleCloseDetail}
  />
{/if}

<SelectSolutionModal
  bind:open={modalOpen}
  solutionNames={Array.from(selectedNames)}
  loading={selectLoading}
  error={selectError}
  onConfirm={handleConfirmSelection}
  onCancel={handleCancelModal}
/>

<style>
  .generate-more-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 160px;
    padding: 1.5rem;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-bg-card);
    cursor: pointer;
    transition: all 200ms ease;
  }
  .generate-more-card:hover:not(:disabled) {
    border-color: var(--color-accent);
    background: linear-gradient(135deg, rgba(229, 90, 40, 0.06) 0%, var(--color-bg-card) 60%);
    transform: translateY(-2px);
    box-shadow: 0 0 0 1px var(--color-accent);
  }
  .generate-more-card:hover:not(:disabled) :global(.group-icon) {
    background: rgba(229, 90, 40, 0.15);
  }
  .generate-more-card:disabled {
    cursor: default;
    opacity: 1;
  }
  .generate-more-card.is-loading {
    border-style: dashed;
    border-color: var(--color-border-emphasis);
  }
</style>

