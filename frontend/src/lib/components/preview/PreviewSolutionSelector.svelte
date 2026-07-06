<script lang="ts">
  import { SvelteSet } from "svelte/reactivity";
  import SolutionGrid from "$lib/components/solutions/SolutionGrid.svelte";
  import CoverageNotes from "$lib/components/CoverageNotes.svelte";
  import SolutionDetail from "$lib/components/SolutionDetail.svelte";
  import SelectSolutionModal from "$lib/components/SelectSolutionModal.svelte";
  import { selectSolution, regenerateIdeas, ApiError } from "$lib/api";
  import { Sparkles, Loader2, Coins } from "lucide-svelte";
  import { DEFAULT_STAGE_COSTS } from "$lib/types/job";
  import type { SolutionPreview, StageCosts } from "$lib/types/job";
  import { solutionDisplayTitle, opportunityShape } from "$lib/utils/solution-utils";
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
    /** Informational coverage/pain-concentration notes for the whole set. */
    coverageNotes?: string[] | null;
    /** Audience framing (output lens): label for the "For {x}" eyebrow + resolved segment to split on. */
    primaryAudience?: string | null;
    audienceLabel?: string | null;
    /** Parent observes the real inline action bar to decide when sticky CTA appears. */
    actionBarRef?: HTMLElement | null;
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
    coverageNotes = [],
    primaryAudience = null,
    audienceLabel = null,
    actionBarRef = $bindable<HTMLElement | null>(null),
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

  // Opportunity shape — one-line read on how this niche's ideas split across GTM angles.
  const shape = $derived(opportunityShape(solutions));

  // Batch-scoped GTM focus for the NEXT regeneration (defaults to the run's original focus = auto).
  const REGEN_FOCUSES = [
    { value: "auto", label: "Auto" },
    { value: "novelty", label: "Novelty" },
    { value: "distribution", label: "Distribution" },
  ] as const;
  let regenerateFocus = $state<"auto" | "novelty" | "distribution">("auto");

  $effect(() => {
    if (!isRegenerating && regenerating) regenerating = false;
  });

  async function handleRegenerate() {
    if (regenerating || isRegenerating) return;
    regenerating = true;
    regenerateError = "";
    try {
      await regenerateIdeas(jobId, regenerateFocus === "auto" ? undefined : regenerateFocus);
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
    {#if (coverageNotes && coverageNotes.length) || shape}
      <div class="selector-context">
        {#if shape}
          <p class="opportunity-shape">
            <span class="opportunity-shape__label">Opportunity shape</span>
            {shape.line}
          </p>
        {/if}
        {#if coverageNotes && coverageNotes.length}
          <CoverageNotes notes={coverageNotes} compact />
        {/if}
      </div>
    {/if}

    <!-- Solutions grid (top-pick + remaining, shared with visitor view) -->
    <SolutionGrid
      {solutions}
      {primaryAudience}
      {audienceLabel}
      onSelect={handleToggle}
      {selectedNames}
      maxSelections={MAX_SELECTIONS}
      {selectLoading}
      voteCounts={solutionVotes}
      onOpen={handleOpenDetail}
    />

    <!-- Generate more ideas -->
    {#if canRegenerate}
      <div class="regen-focus" role="group" aria-label="Idea focus for the next batch">
        {#each REGEN_FOCUSES as focus}
          <button
            type="button"
            onclick={() => regenerateFocus = focus.value}
            disabled={regenerating || isRegenerating}
            class="regen-focus-btn {regenerateFocus === focus.value ? 'is-active' : ''}"
          >
            {focus.label}
          </button>
        {/each}
      </div>
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
    <div class="selection-bar" bind:this={actionBarRef}>
      <span class="selection-count">
        {#if selectionCount === 0}
          Choose 1–3 solutions to compare
        {:else}
          {selectionCount} selected · {stageCosts.deep_research} credits · one-time per niche
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

  .selector-context {
    display: grid;
    gap: var(--space-3);
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
    border: 1px solid var(--color-border-accent);
    border-radius: var(--radius-md);
    background: color-mix(in srgb, var(--color-accent) 5%, var(--color-bg-elevated));
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

  .opportunity-shape {
    margin: 0 0 var(--space-3);
    font-size: var(--text-sm);
    color: var(--color-text-secondary);
    line-height: 1.5;
  }

  .opportunity-shape__label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
    margin-right: var(--space-2);
  }

  .regen-focus {
    align-self: center;
    display: inline-flex;
    gap: var(--space-1);
    margin-bottom: var(--space-2);
  }

  .regen-focus-btn {
    padding: 0.2rem var(--space-2);
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    cursor: pointer;
    transition: border-color 0.15s ease, color 0.15s ease;
  }

  .regen-focus-btn:hover:not(:disabled) {
    color: var(--color-text-secondary);
    border-color: var(--color-border-emphasis);
  }

  .regen-focus-btn.is-active {
    background: color-mix(in srgb, var(--color-accent) 10%, transparent);
    border-color: color-mix(in srgb, var(--color-accent) 40%, transparent);
    color: var(--color-accent);
    font-weight: 500;
  }

  .regen-focus-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
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
