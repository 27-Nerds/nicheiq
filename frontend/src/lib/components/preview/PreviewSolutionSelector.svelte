<script lang="ts">
  import { SvelteSet } from "svelte/reactivity";
  import SolutionGrid from "$lib/components/solutions/SolutionGrid.svelte";
  import SolutionDetail from "$lib/components/SolutionDetail.svelte";
  import SelectSolutionModal from "$lib/components/SelectSolutionModal.svelte";
  import { selectSolution, regenerateIdeas, ApiError } from "$lib/api";
  import { Sparkles, Loader2, Coins } from "lucide-svelte";
  import { DEFAULT_STAGE_COSTS } from "$lib/types/job";
  import type { SolutionPreview, StageCosts } from "$lib/types/job";
  import { solutionDisplayTitle } from "$lib/utils/solution-utils";
  import { creditTopUp } from "$lib/stores/creditTopUp.svelte";

  const MAX_SELECTIONS = 3;

  interface Props {
    jobId: string;
    solutions: SolutionPreview[];
    creditBalance: number;
    stageCosts: StageCosts;
    canRegenerate?: boolean;
    isRegenerating?: boolean;
    onComplete?: () => void;
    onSelectionComplete?: () => void;
    onRegenerateStart?: () => void;
    onSelectionChange?: (info: { count: number; canAfford: boolean; names: string[] }) => void;
    externalValidate?: number;
    selectedSolutions?: string[];
    solutionVotes?: Record<string, number>;
  }

  let {
    jobId,
    solutions,
    creditBalance,
    stageCosts = { ...DEFAULT_STAGE_COSTS },
    canRegenerate = false,
    isRegenerating = false,
    onComplete,
    onSelectionComplete,
    onRegenerateStart,
    onSelectionChange,
    externalValidate = $bindable(0),
    selectedSolutions,
    solutionVotes = {},
  }: Props = $props();

  // Multi-select state
  let selectedNames = new SvelteSet<string>();
  let modalOpen = $state(false);
  let selectLoading = $state(false);
  let selectError = $state("");
  let modalIndex = $state<number | null>(null);

  // Restore pre-existing selections from prop (e.g., page reload during selection)
  $effect(() => {
    if (selectedSolutions?.length && selectedNames.size === 0) {
      for (const name of selectedSolutions) selectedNames.add(name);
    }
  });

  // Regeneration state
  let regenerating = $state(false);
  let regenerateError = $state("");
  const canAffordRegenerate = $derived(creditBalance >= stageCosts.regenerate_ideas);

  $effect(() => {
    if (!isRegenerating && regenerating) regenerating = false;
  });

  async function handleRegenerate() {
    if (regenerating || isRegenerating) return;
    regenerating = true;
    regenerateError = "";
    try {
      await regenerateIdeas(jobId);
      onRegenerateStart?.();
    } catch (e) {
      if (e instanceof ApiError && e.status === 402) {
        creditTopUp.show({
          balance: creditBalance,
          required: stageCosts.regenerate_ideas,
          stageName: "idea regeneration",
        });
      } else {
        regenerateError = e instanceof Error ? e.message : "Failed to generate ideas";
      }
      regenerating = false;
    }
  }

  // Notify parent when selection state changes
  $effect(() => {
    const count = selectedNames.size;
    const canAfford = creditBalance >= stageCosts.deep_research;
    const names = [...selectedNames];
    onSelectionChange?.({ count, canAfford, names });
  });

  // React to external validate trigger (e.g., from sticky bar)
  let lastValidateTrigger = 0;
  $effect(() => {
    if (externalValidate > lastValidateTrigger) {
      lastValidateTrigger = externalValidate;
      handleValidateClick();
    }
  });

  // Top-pick + remaining split now lives in SolutionGrid.svelte

  const selectionCount = $derived(selectedNames.size);
  const canSubmit = $derived(selectionCount > 0);
  const canAffordDeepResearch = $derived(
    creditBalance >= stageCosts.deep_research,
  );

  /** 1-based selection order. 0 if not selected. */
  function selectionIndexOf(name: string): number {
    let i = 1;
    for (const n of selectedNames) {
      if (n === name) return i;
      i++;
    }
    return 0;
  }

  function handleToggle(name: string) {
    if (selectLoading) return;
    if (selectedNames.has(name)) {
      selectedNames.delete(name);
    } else if (selectedNames.size < MAX_SELECTIONS) {
      selectedNames.add(name);
    }
  }

  function handleValidateClick() {
    if (!canSubmit) return;
    if (!canAffordDeepResearch) {
      creditTopUp.show({
        balance: creditBalance,
        required: stageCosts.deep_research,
        stageName: "deep research",
      });
      return;
    }
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
      onComplete?.();
      onSelectionComplete?.();
    } catch (e) {
      if (e instanceof ApiError && e.status === 402) {
        modalOpen = false;
        creditTopUp.show({
          balance: creditBalance,
          required: stageCosts.deep_research,
          stageName: "deep research",
        });
      } else {
        selectError =
          e instanceof Error ? e.message : "Failed to select solution";
      }
    } finally {
      selectLoading = false;
    }
  }

  function handleCancelModal() {
    if (!selectLoading) {
      modalOpen = false;
      selectError = "";
    }
  }

  function handleOpenDetail(index: number) {
    modalIndex = index;
  }

  function handleNavigate(index: number) {
    modalIndex = index;
  }

  function handleCloseDetail() {
    modalIndex = null;
  }

  // Display name map for modal
  const displayNameMap = $derived(
    new Map(solutions.map((s) => [s.solution_name, solutionDisplayTitle(s)])),
  );
</script>

<div class="selector-root">
  {#if solutions.length === 0}
    <p class="empty-state">
      No solutions available yet.
      <a href="/jobs/{jobId}" class="fallback-link">Go to job page</a>
    </p>
  {:else}
    <!-- Solutions grid (top-pick + remaining, shared with visitor view) -->
    <SolutionGrid
      {solutions}
      onSelect={handleToggle}
      {selectedNames}
      maxSelections={MAX_SELECTIONS}
      {selectLoading}
      voteCounts={solutionVotes}
      onOpen={handleOpenDetail}
    />

    <!-- Generate more ideas -->
    {#if canRegenerate}
      <button
        onclick={handleRegenerate}
        disabled={regenerating || isRegenerating || !canAffordRegenerate}
        class="generate-more-btn"
      >
        {#if regenerating || isRegenerating}
          <Loader2 class="w-4 h-4 animate-spin" />
          <span>Exploring new angles...</span>
        {:else}
          <Sparkles class="w-4 h-4" />
          <span>Generate more ideas</span>
          {#if stageCosts.regenerate_ideas > 0}
            <span class="generate-cost"><Coins class="w-3 h-3" />{stageCosts.regenerate_ideas} credits</span>
          {/if}
        {/if}
      </button>
    {/if}
    {#if regenerateError}
      <p class="regenerate-error">{regenerateError}</p>
    {/if}

    <!-- Selection action bar (always visible; disabled state when 0 selected) -->
    <div class="selection-bar">
      <span class="selection-count">
        {#if selectionCount === 0}
          Choose 1–3 solutions to compare
        {:else}
          {selectionCount} selected · {stageCosts.deep_research} credits
        {/if}
      </span>

      {#if !canAffordDeepResearch && selectionCount > 0}
        <span class="credit-warning">
          {stageCosts.deep_research - creditBalance} more credits needed
        </span>
      {/if}

      <button
        class="validate-btn"
        disabled={!canSubmit || selectLoading}
        onclick={handleValidateClick}
      >
        {#if selectLoading}
          Validating...
        {:else if !canAffordDeepResearch && selectionCount > 0}
          Add credits to start
        {:else}
          Start Deep Research
        {/if}
      </button>
    </div>

    <!-- Fallback link -->
    <p class="fallback">
      <a href="/jobs/{jobId}" class="fallback-link">
        Want different options? Explore all solutions on the job page &rarr;
      </a>
    </p>
  {/if}
</div>

<!-- Confirmation modal -->
<SelectSolutionModal
  bind:open={modalOpen}
  solutionNames={Array.from(selectedNames)}
  {solutions}
  loading={selectLoading}
  error={selectError}
  creditCost={stageCosts.deep_research}
  onConfirm={handleConfirmSelection}
  onCancel={handleCancelModal}
/>

<!-- Detail modal -->
{#if modalIndex !== null && solutions[modalIndex]}
  <SolutionDetail
    open={modalIndex !== null}
    solution={solutions[modalIndex]}
    {solutions}
    currentIndex={modalIndex}
    isSelected={selectedNames.has(solutions[modalIndex].solution_name)}
    selectionIndex={selectionIndexOf(solutions[modalIndex].solution_name)}
    maxReached={selectedNames.size >= MAX_SELECTIONS}
    disabled={selectLoading}
    onSelect={handleToggle}
    onNavigate={handleNavigate}
    onClose={handleCloseDetail}
    voteCount={solutionVotes[solutions[modalIndex].solution_name] ?? 0}
  />
{/if}

<style>
  .selector-root {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .empty-state {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--color-text-muted);
    text-align: center;
    padding: var(--space-8) 0;
  }

  /* Grid styles moved to SolutionGrid.svelte */

  /* Selection action bar (always visible) */
  .selection-bar {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-bg-surface);
  }

  .selection-count {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--color-text-primary);
    white-space: nowrap;
  }

  .credit-warning {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--color-warning-dark, #a16207);
    white-space: nowrap;
  }

  .validate-btn {
    margin-left: auto;
    padding: var(--space-2) var(--space-4);
    background: var(--color-accent);
    color: white;
    border: none;
    border-radius: var(--radius-md);
    font-family: var(--font-display);
    font-size: var(--text-sm);
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
    transition: background-color 0.15s ease;
    min-height: 40px;
  }

  .validate-btn:hover:not(:disabled) {
    background: var(--color-accent-hover);
  }

  .validate-btn:active:not(:disabled) {
    transform: scale(0.98);
  }

  .validate-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  @media (max-width: 639px) {
    .selection-count { white-space: normal; }
    .validate-btn { margin-left: 0; width: 100%; }
  }

  .fallback {
    text-align: center;
    padding: var(--space-2) 0;
  }

  .fallback-link {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--color-text-muted);
    text-decoration: none;
    letter-spacing: 0.02em;
    transition: color 0.15s ease;
  }

  .fallback-link:hover {
    color: var(--color-text-secondary);
  }

  .generate-more-btn {
    align-self: center;
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-4);
    background: transparent;
    border: 1px dashed var(--color-border);
    border-radius: var(--radius-md);
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 500;
    cursor: pointer;
    transition: border-color 0.15s ease, color 0.15s ease;
  }

  .generate-more-btn:hover:not(:disabled) {
    border-color: var(--color-accent);
    color: var(--color-accent);
  }

  .generate-more-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .generate-cost {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    color: var(--color-text-muted);
  }

  .regenerate-error {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--color-error);
    text-align: center;
  }
</style>
