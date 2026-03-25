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

  import AlertBanner from "$lib/components/ui/AlertBanner.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";
  import AnimateOnScroll from "$lib/components/ui/AnimateOnScroll.svelte";
  import { DEFAULT_STAGE_COSTS } from "$lib/types/job";
  import type { SolutionPreview, StageCosts } from "$lib/types/job";
  import { selectSolution, regenerateIdeas, ApiError } from "$lib/api";
  import { invalidateAll } from "$app/navigation";
  import { tick } from "svelte";
  import { SvelteSet } from "svelte/reactivity";
  import { Coins } from "lucide-svelte";
  import { computeCompositeScore, solutionDisplayTitle } from "$lib/utils/solution-utils";
  import { creditTopUp } from "$lib/stores/creditTopUp.svelte";



  const MAX_SELECTIONS = 3;

  interface Props {
    jobId: string;
    solutions: SolutionPreview[];
    selectedSolution?: string | null;
    selectedSolutions?: string[] | null;
    isRegenerating?: boolean;
    canRegenerate?: boolean;
    stageCosts?: StageCosts;
    creditBalance?: number;
    onSelectionComplete?: () => void;
    onRegenerateStart?: () => void;
    solutionVotes?: Record<string, number>;
  }

  let {
    jobId,
    solutions = $bindable(),
    selectedSolution = null,
    selectedSolutions = null,
    isRegenerating = false,
    canRegenerate = true,
    stageCosts = { ...DEFAULT_STAGE_COSTS },
    creditBalance = 0,
    onSelectionComplete,
    onRegenerateStart,
    solutionVotes = {},
  }: Props = $props();

  // Track user's multi-select choices (before confirmation)
  let selectedNames = new SvelteSet<string>();

  /** 1-based selection order, 0 if not selected. Set iteration follows insertion order (ES6). */
  function selectionIndexOf(name: string): number {
    let i = 1;
    for (const n of selectedNames) {
      if (n === name) return i;
      i++;
    }
    return 0;
  }
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
      const scrollTimer = setTimeout(() => {
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
      const badgeTimer = setTimeout(() => { showNewBadges = false; }, 8000);

      return () => { clearTimeout(scrollTimer); clearTimeout(badgeTimer); };
    }
  });

  // Track solution count at regeneration start for success/failure detection
  let solutionCountAtRegenStart = $state(solutions.length);

  // Detect regeneration failure via SSE state transitions
  $effect(() => {
    if (isRegenerating) {
      // SSE confirms backend is regenerating — hand off from local state
      regenerating = false;
      if (!wasRegenerating) {
        // Entering regeneration: snapshot current count and reset batch UI
        solutionCountAtRegenStart = solutions.length;
        originalBatchSize = solutions.length;
        hasRevealedNewBatch = false;
      }
      wasRegenerating = true;
    } else if (wasRegenerating) {
      // isRegenerating just went false. Was it success or failure?
      wasRegenerating = false;
      // If no new solutions appeared, regeneration failed
      if (solutions.length <= solutionCountAtRegenStart) {
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

  // Advisory credit checks — UI hints only, backend 402 is authoritative
  const canAffordDeepResearch = $derived(creditBalance >= stageCosts.deep_research);
  const canAffordRegenerate = $derived(creditBalance >= stageCosts.regenerate_ideas);
  const canAffordBoth = $derived(creditBalance >= stageCosts.deep_research + stageCosts.regenerate_ideas);
  const balanceAfterDeep = $derived(creditBalance - stageCosts.deep_research);
  const canAffordLandingAfterDeep = $derived(balanceAfterDeep >= stageCosts.landing_page);


  function openTopUp(required: number, stageName: string) {
    creditTopUp.show({ balance: creditBalance, required, stageName });
  }

  // Regen confirmation state
  let regenConfirmPending = $state(false);

  // Reset confirmation if external state changes make it irrelevant
  $effect(() => {
    if (regenConfirmPending && (isRegenerating || canAffordBoth || !canAffordRegenerate)) {
      regenConfirmPending = false;
    }
  });

  // Identify highest-viability solution
  const topPickName = $derived.by(() => {
    if (solutions.length === 0) return null;
    let best = solutions[0];
    for (const s of solutions) {
      if (computeCompositeScore(s) > computeCompositeScore(best)) best = s;
    }
    return best.solution_name;
  });

  // Map solution_name → display title for pills
  const displayNameMap = $derived(new Map(solutions.map(s => [s.solution_name, solutionDisplayTitle(s)])));

  // Dynamic header narrative based on selection count
  const headerNarrative = $derived.by(() => {
    if (alreadySubmitted) return { title: 'Validation in Progress', subtitle: 'Check your email in ~20 minutes for your full report.' };
    if (isRegenerating) return { title: 'Generating New Solutions...', subtitle: 'New solutions are being generated and will be added to your options shortly.' };
    if (selectionCount > 0 && !canAffordDeepResearch) {
      return {
        title: selectionCount >= MAX_SELECTIONS ? 'Picks locked in' : 'Good picks so far',
        subtitle: 'Your selections are saved. Add credits to unlock the full validation — market demand, competition, pricing, and launch strategy.'
      };
    }
    switch (selectionCount) {
      case 0: return { title: 'Choose Your Solutions', subtitle: `Pick up to ${MAX_SELECTIONS} ideas to validate. We'll analyze market demand, competition, and pricing — you'll know which one is worth building.` };
      case 1: return { title: 'Good first pick', subtitle: `Add 1–2 more to compare against. The report will show which has the strongest market.` };
      case 2: return { title: 'Strong shortlist', subtitle: `Add a third or validate now — either way, you'll get a clear winner.` };
      default: return { title: 'Ready to validate', subtitle: `All ${MAX_SELECTIONS} slots filled. Hit validate and we'll find your strongest market opportunity.` };
    }
  });

  function handleToggle(name: string) {
    if (alreadySubmitted || selectLoading || isRegenerating) return;

    if (selectedNames.has(name)) {
      selectedNames.delete(name);
    } else if (selectedNames.size < MAX_SELECTIONS) {
      selectedNames.add(name);
    }
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

  function handleValidateClick() {
    if (selectionCount > 0 && !canAffordDeepResearch) {
      openTopUp(stageCosts.deep_research, 'deep research');
    } else {
      handleSubmitClick();
    }
  }

  function handleSubmitClick() {
    if (!canSubmit) return;
    selectError = "";
    // Always show confirmation modal so all users see the outcome checklist
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
      if (e instanceof ApiError && e.status === 402) {
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
    modalOpen = false;
    selectError = "";
  }

  async function handleRegenerateClick() {
    if (!canAffordBoth && canAffordDeepResearch && canAffordRegenerate) {
      regenConfirmPending = true;
      await tick();
      document.getElementById('regen-confirm-cancel')?.focus();
    } else {
      handleRegenerate();
    }
  }

  function handleRegenConfirm() {
    regenConfirmPending = false;
    handleRegenerate();
  }

  function handleRegenCancel() {
    regenConfirmPending = false;
  }

  async function handleRegenerate() {
    if (regenerating) return;
    regenerating = true;
    regenerateError = "";

    try {
      await regenerateIdeas(jobId);
      onRegenerateStart?.();
      invalidateAll();
      // Keep regenerating=true — SSE will set isRegenerating, then new cards arrive and button disappears
    } catch (e) {
      if (e instanceof ApiError && e.status === 402) {
        creditTopUp.show({
          balance: creditBalance,
          required: stageCosts.regenerate_ideas,
          stageName: "idea regeneration",
        });
      } else {
        regenerateError =
          e instanceof Error ? e.message : "Failed to regenerate ideas";
      }
      regenerating = false;
    }
  }
</script>

<div>
  <!-- Header card (sticky below nav) -->
  <div class="card p-3 sticky top-14 z-30 selection-header">
    <div class="flex flex-wrap items-start gap-3">
      <div class="p-2 rounded-xl bg-accent/10 border border-accent/20 shrink-0">
        <Lightbulb class="w-4 h-4 text-accent" />
      </div>
      <div class="flex-1 min-w-0">
        <h2 class="text-lg font-semibold text-text-primary">
          {headerNarrative.title}
        </h2>
        <p class="mt-1 text-sm text-text-secondary min-h-[42px]">
          {#if alreadySubmitted}
            {#if submittedNames.size === 1}
              You selected <span class="font-medium text-text-primary">{[...submittedNames][0]}</span>. {headerNarrative.subtitle}
            {:else}
              You selected {submittedNames.size} solutions. {headerNarrative.subtitle}
            {/if}
          {:else}
            {headerNarrative.subtitle}
          {/if}
        </p>
      </div>

      <!-- Selection counter + submit button -->
      {#if !alreadySubmitted && !isRegenerating}
        <div class="flex flex-col items-end gap-2 shrink-0 w-full sm:w-auto">
          <div class="flex items-center gap-3 w-full sm:w-auto">
            <div class="flex items-center gap-2">
              <div class="flex items-center gap-1" aria-hidden="true">
                {#each Array(MAX_SELECTIONS) as _, i}
                  <span class="w-1.5 h-1.5 rounded-full transition-colors duration-200
                    {i < selectionCount ? 'bg-accent' : 'bg-border-emphasis'}"></span>
                {/each}
              </div>
              <span class="text-sm font-medium text-accent tabular-nums">
                {selectionCount}/{MAX_SELECTIONS}
              </span>
            </div>
            <SubmitButton
              onclick={handleValidateClick}
              disabled={selectionCount === 0}
              loading={selectLoading}
              loadingText="Starting analysis..."
              icon={selectionCount > 0 ? ArrowRight : undefined}
              iconPosition="end"
              label={selectionCount === 0
                ? 'Pick 1–3 solutions to start validation'
                : 'Validate my picks'}
              type="button"
              class={selectionCount === 0
                ? 'btn-dashed w-full sm:w-auto'
                : 'btn-primary w-full sm:w-auto'}
            >
              {#snippet suffix()}
                {#if selectionCount > 0}
                  <span class="inline-flex items-center gap-1 text-xs opacity-80">
                    <Coins class="w-3 h-3" />
                    {#if canAffordDeepResearch}
                      {stageCosts.deep_research}
                    {:else}
                      {stageCosts.deep_research - creditBalance} needed
                    {/if}
                  </span>
                {/if}
              {/snippet}
            </SubmitButton>
          </div>
          <div class="hidden sm:flex items-center gap-2 text-[10px] text-text-muted">
            <span class="flex items-center gap-1">
              <span class="w-4 h-4 rounded-full bg-accent/20 border border-accent/40 text-accent font-bold flex items-center justify-center" style="font-size:8px">1</span>
              Select
            </span>
            <span class="w-4 h-px bg-border-emphasis"></span>
            <span class="flex items-center gap-1 text-text-secondary">
              <span class="w-4 h-4 rounded-full bg-accent/20 border border-accent/40 text-accent font-bold flex items-center justify-center" style="font-size:8px">2</span>
              We analyze (~20 min)
            </span>
            <span class="w-4 h-px bg-border-emphasis"></span>
            <span class="flex items-center gap-1">
              <span class="w-4 h-4 rounded-full bg-accent/20 border border-accent/40 text-accent font-bold flex items-center justify-center" style="font-size:8px">3</span>
              Full validation report
            </span>
          </div>
          {#if !canAffordDeepResearch && !alreadySubmitted}
            <p class="text-xs text-text-muted flex items-center gap-1.5">
              <Coins class="w-3 h-3 text-accent shrink-0" />
              You have {creditBalance} credits — validation costs {stageCosts.deep_research}.
            </p>
          {:else if canAffordDeepResearch && !canAffordLandingAfterDeep && !alreadySubmitted}
            <p class="text-xs text-text-muted mt-1">This uses all your remaining credits. Landing page ({stageCosts.landing_page} credits) will need more.</p>
          {/if}
        </div>
      {/if}
    </div>
    {#if !alreadySubmitted}
      <div class="flex flex-wrap items-center gap-1.5 mt-2 min-h-[28px]">
        {#each [...selectedNames] as name, i}
          <span class="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-accent/8 border border-accent/20 text-accent font-medium max-w-[200px]">
            <span class="inline-flex items-center justify-center w-4 h-4 rounded shrink-0 bg-accent text-white text-[10px] font-bold tabular-nums">{i + 1}</span>
            <span class="truncate">{displayNameMap.get(name) || name}</span>
            <button
              type="button"
              class="ml-0.5 hover:text-accent-hover transition-colors shrink-0"
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

  <div class="space-y-6 mt-6">
  <!-- Credit warning banners -->
  {#if !alreadySubmitted && !isRegenerating}
    {#if !canAffordBoth && canAffordDeepResearch}
      <AlertBanner
        variant="warning"
        title="Budget check"
      >
        {#snippet children()}
          <p class="text-sm text-text-muted mt-1">
            {creditBalance} credits remaining. Deep analysis ({stageCosts.deep_research}) or new ideas ({stageCosts.regenerate_ideas}) &mdash; pick one.
            <button type="button" onclick={() => openTopUp(stageCosts.deep_research, 'deep research')} class="text-accent hover:text-accent-hover font-medium">Add credits &rarr;</button>
          </p>
        {/snippet}
      </AlertBanner>
    {/if}
  {/if}

  <!-- Solution Cards Grid -->
  <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
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
          isTopPick={!alreadySubmitted && solution.solution_name === topPickName}
          voteCount={solutionVotes[solution.solution_name] ?? 0}
          selectionIndex={alreadySubmitted ? 0 : selectionIndexOf(solution.solution_name)}
        />
      </AnimateOnScroll>
    {/each}

    <!-- Generate More card (last grid cell) -->
    {#if !alreadySubmitted}
      <AnimateOnScroll animation="fade-up" delay={100 + Math.floor(solutions.length / 3) * 150} duration={500} once={true}>
        {#if regenConfirmPending}
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <div
            class="generate-more-card h-full w-full !cursor-default"
            onkeydown={(e) => { if (e.key === 'Escape') handleRegenCancel(); }}
          >
            <div class="w-full p-3 rounded-lg bg-warning/10 border border-warning/20">
              <p class="text-sm text-text-primary font-medium">Heads up</p>
              <p class="text-xs text-text-muted mt-1">
                Generating ideas costs {stageCosts.regenerate_ideas} credits. You'll have {creditBalance - stageCosts.regenerate_ideas} left &mdash; not enough for deep analysis ({stageCosts.deep_research}). Continue?
              </p>
              <div class="flex items-center gap-2 mt-3">
                <button
                  onclick={handleRegenConfirm}
                  disabled={regenerating || isRegenerating}
                  class="btn-primary px-3 py-1.5 text-xs font-medium rounded-md"
                >
                  Generate Anyway
                </button>
                <button
                  id="regen-confirm-cancel"
                  onclick={handleRegenCancel}
                  class="btn-secondary px-3 py-1.5 text-xs font-medium rounded-md"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        {:else}
          <button
            onclick={handleRegenerateClick}
            disabled={regenerating || isRegenerating || !canAffordRegenerate}
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
            {:else if !canAffordRegenerate}
              <div class="p-2.5 rounded-xl bg-amber-500/10">
                <Sparkles class="w-5 h-5 text-amber-500" />
              </div>
              <span class="text-sm font-semibold text-text-primary mt-2.5">Generate More Ideas</span>
              <span class="text-xs text-text-muted mt-1 inline-flex items-center gap-1">
                <Coins class="w-3 h-3" />Costs {stageCosts.regenerate_ideas} credits &middot; You have {creditBalance}
              </span>
              <!-- svelte-ignore a11y_no_static_element_interactions -->
              <span
                role="link"
                tabindex="0"
                class="mt-2 inline-flex items-center gap-1 text-xs font-medium text-accent hover:text-accent-hover transition-colors cursor-pointer"
                onclick={(e) => { e.stopPropagation(); openTopUp(stageCosts.regenerate_ideas, 'idea regeneration'); }}
                onkeydown={(e) => { if (e.key === 'Enter') { e.stopPropagation(); openTopUp(stageCosts.regenerate_ideas, 'idea regeneration'); } }}
              >
                Get more credits <ArrowRight class="w-3 h-3" />
              </span>
            {:else}
              <div class="p-2.5 rounded-xl bg-accent/10 group-icon">
                <Sparkles class="w-5 h-5 text-accent" />
              </div>
              <span class="text-sm font-semibold text-text-primary mt-2.5">Generate More Ideas</span>
              {#if stageCosts.regenerate_ideas > 0}
                <span class="text-xs text-text-muted mt-0.5 inline-flex items-center gap-1"><Coins class="w-3 h-3" />{stageCosts.regenerate_ideas} credits</span>
              {/if}
            {/if}
          </button>
        {/if}
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
    voteCount={solutionVotes[solutions[modalIndex].solution_name] ?? 0}
    selectionIndex={alreadySubmitted ? 0 : selectionIndexOf(solutions[modalIndex].solution_name)}
  />
{/if}

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

<style>
  /* Stabilize sticky header height so grid doesn't jump on selection changes */
  .selection-header {
    min-height: 5.5rem;
  }

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

