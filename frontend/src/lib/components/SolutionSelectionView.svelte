<script lang="ts">
  import {
    Loader2,
    RefreshCw,
    Lightbulb,
    AlertCircle,
    ArrowRight,
  } from "lucide-svelte";
  import SolutionCard from "./SolutionCard.svelte";
  import SelectSolutionModal from "./SelectSolutionModal.svelte";
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
  }

  let {
    jobId,
    solutions = $bindable(),
    selectedSolution = null,
    selectedSolutions = null,
    isRegenerating = false,
    canRegenerate = true,
    onSelectionComplete,
  }: Props = $props();

  // Track user's multi-select choices (before confirmation)
  let selectedNames = $state<Set<string>>(new Set());
  let modalOpen = $state(false);
  let selectLoading = $state(false);
  let selectError = $state("");
  let regenerating = $state(false);
  let regenerateError = $state("");

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
    } catch (e) {
      regenerateError =
        e instanceof Error ? e.message : "Failed to regenerate ideas";
    } finally {
      regenerating = false;
    }
  }
</script>

<div class="space-y-6">
  <!-- Header -->
  <div class="card p-6">
    <div class="flex items-start gap-4">
      <div class="p-3 rounded-xl bg-accent/10 border border-accent/20 shrink-0">
        <Lightbulb class="w-6 h-6 text-accent" />
      </div>
      <div class="flex-1">
        <h2 class="text-lg font-semibold text-text-primary">
          {#if alreadySubmitted}
            Solution{submittedNames.size > 1 ? 's' : ''} Selected
          {:else if isRegenerating}
            Generating New Solutions...
          {:else}
            Choose Your Solutions
          {/if}
        </h2>
        <p class="mt-1 text-sm text-text-secondary">
          {#if alreadySubmitted}
            {#if submittedNames.size === 1}
              You selected <span class="font-medium text-text-primary">{[...submittedNames][0]}</span>. Deep analysis is in progress.
            {:else}
              You selected {submittedNames.size} solutions for deep analysis. The system will evaluate all and pick the best for your report.
            {/if}
          {:else if isRegenerating}
            New solutions are being generated and will be added to your options shortly.
          {:else}
            Select 1 to {MAX_SELECTIONS} solutions for deep analysis. The system will evaluate all selected and choose the best one for your final report.
          {/if}
        </p>
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
  <div class="grid gap-4">
    {#each solutions as solution}
      <SolutionCard
        {solution}
        onSelect={handleToggle}
        disabled={alreadySubmitted || selectLoading || isRegenerating}
        isSelected={alreadySubmitted
          ? submittedNames.has(solution.solution_name)
          : selectedNames.has(solution.solution_name)}
        maxReached={!alreadySubmitted && selectionCount >= MAX_SELECTIONS}
      />
    {/each}
  </div>

  <!-- Regenerate Section -->
  {#if !alreadySubmitted && canRegenerate && !isRegenerating}
    <div class="card p-5">
      <div class="flex items-center justify-between gap-4">
        <div>
          <h3 class="text-sm font-medium text-text-primary">
            Not what you're looking for?
          </h3>
          <p class="mt-1 text-sm text-text-muted">
            Generate a new batch of solutions. You can do this once.
          </p>
        </div>
        <button
          onclick={handleRegenerate}
          disabled={regenerating}
          class="btn-secondary px-4 py-2 text-sm font-medium rounded-lg flex items-center gap-2 shrink-0 disabled:opacity-50"
        >
          {#if regenerating}
            <Loader2 class="w-4 h-4 animate-spin motion-reduce:animate-none" />
            Generating...
          {:else}
            <RefreshCw class="w-4 h-4" />
            Generate New Ideas
          {/if}
        </button>
      </div>
      {#if regenerateError}
        <div class="mt-3 flex items-center gap-2 p-3 bg-error/10 border border-error/20 rounded-lg text-error text-sm">
          <AlertCircle class="w-4 h-4 shrink-0" />
          <span>{regenerateError}</span>
        </div>
      {/if}
    </div>
  {/if}
</div>

<SelectSolutionModal
  bind:open={modalOpen}
  solutionNames={Array.from(selectedNames)}
  loading={selectLoading}
  error={selectError}
  onConfirm={handleConfirmSelection}
  onCancel={handleCancelModal}
/>
