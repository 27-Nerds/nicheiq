<script lang="ts">
  import type { Snippet } from "svelte";
  import { untrack } from "svelte";
  import {
    ChevronLeft,
    ChevronRight,
    X,
  } from "lucide-svelte";
  import { portal } from "$lib/actions/portal";
  import Badge from "$lib/components/ui/Badge.svelte";
  import SolutionDetailContent from "$lib/components/SolutionDetailContent.svelte";
  import Popover from "$lib/components/ui/Popover.svelte";
  import { scoreRationale } from "$lib/utils/scoreRationale";
  import { SCORE_DEFINITIONS } from "$lib/utils/scoreDefinitions";
  import type { SolutionPreview } from "$lib/types/job";
  import { computeCompositeScore, solutionStrengthBadge, solutionDisplayTitle, originalityMetric } from "$lib/utils/solution-utils";

  interface Props {
    open: boolean;
    solution: SolutionPreview;
    solutions: SolutionPreview[];
    currentIndex: number;
    isSelected?: boolean;
    disabled?: boolean;
    maxReached?: boolean;
    selectionIndex?: number;
    selectedCount?: number;
    maxSelections?: number;
    canStart?: boolean;
    canAffordStart?: boolean;
    startCost?: number | null;
    onSelect?: (name: string) => void;
    onStartValidation?: () => void;
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
    selectedCount = 0,
    maxSelections = 3,
    canStart = false,
    canAffordStart = true,
    startCost = null,
    onSelect,
    onStartValidation,
    onNavigate,
    onClose,
    actionSlot,
    voteCount = 0,
  }: Props = $props();

  let modalEl: HTMLDivElement | undefined = $state();
  let bodyEl: HTMLDivElement | undefined = $state();

  // Overview = shortlist-decision snapshot; detail = the 7-card deep reference.
  let activeTab = $state<"overview" | "detail">("overview");
  let starting = $state(false); // guards double-submit + shows a pending Start CTA

  // Reset to Overview and scroll to top whenever the pager moves to another idea.
  $effect(() => {
    solution.solution_name;
    untrack(() => {
      activeTab = "overview";
      starting = false;
      if (bodyEl) bodyEl.scrollTop = 0;
    });
  });

  function setTab(tab: "overview" | "detail") {
    activeTab = tab;
    if (bodyEl) bodyEl.scrollTop = 0; // don't land mid-content when the view swaps
  }

  // On open, move focus into the dialog and remember the trigger; on close, return
  // focus to it so keyboard users aren't dumped at the top of the page.
  $effect(() => {
    if (open && modalEl) {
      const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      modalEl.focus();
      return () => trigger?.focus?.();
    }
  });

  const total = $derived(solutions.length);

  const compositeScore = $derived(computeCompositeScore(solution));
  const compositeWhy = $derived(scoreRationale(solution, "composite"));

  // Score color (matches ProgressRing auto logic)
  const scoreColor = $derived.by(() => {
    if (compositeScore >= 0.7) return 'var(--color-success-dark)';
    if (compositeScore < 0.35) return 'var(--color-text-muted)';
    return 'var(--color-text-primary)';
  });

  // Per-score color
  function individualScoreColor(value: number | null | undefined): string {
    if (value == null) return 'var(--color-text-muted)';
    if (value >= 0.7) return 'var(--color-success-dark)';
    if (value >= 0.45) return 'var(--color-text-primary)';
    return 'var(--color-text-muted)';
  }

  const origMetric = $derived(originalityMetric(solution));

  const individualScores = $derived([
    { label: "Market", value: solution.market_fit_score, def: SCORE_DEFINITIONS.market_fit, why: scoreRationale(solution, "market_fit") },
    { label: "Feasible", value: solution.technical_feasibility_score, def: SCORE_DEFINITIONS.technical_feasibility, why: scoreRationale(solution, "technical_feasibility") },
    { label: "SEO", value: solution.seo_scalability_score, def: SCORE_DEFINITIONS.seo, why: scoreRationale(solution, "seo") },
    { label: origMetric.short === "Orig" ? "Original" : (origMetric.short ?? "Original"), value: origMetric.value, def: SCORE_DEFINITIONS.originality, why: scoreRationale(solution, "novelty") },
    { label: "Solo", value: solution.solo_dev_feasibility, def: SCORE_DEFINITIONS.solo_dev, why: scoreRationale(solution, "solo_dev") },
  ]);

  // Backend-sourced strength badge (tags.primary_strength); legacy fallback for pre-tags data.
  const superpower = $derived(solutionStrengthBadge(solution, true));

  const displayTitle = $derived(solutionDisplayTitle(solution));
  const hasHeadline = $derived(!!solution.headline?.trim());

  const isToggleable = $derived(!!onSelect && !disabled && (isSelected || !maxReached));
  const shortlistStatus = $derived(`${selectedCount}/${maxSelections} shortlisted`);
  const startLabel = $derived(
    !canStart
      ? "Shortlist to start"
      : !canAffordStart
        ? "Add credits to start"
        : "Start Deep Research",
  );

  function handleSelect() {
    if (!isToggleable || !onSelect) return;
    onSelect(solution.solution_name);
  }

  function handleStartValidation() {
    if (!onStartValidation || !canStart || disabled || starting) return;
    starting = true; // pending state; reset if the pager moves to another idea
    onStartValidation();
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
    if (e.key === 'Tab') { trapTab(e); return; }
    // Arrow paging only when focus isn't in a control that uses arrows itself
    // (form fields, or the tablist — where arrows belong to tab switching, not paging).
    const t = e.target as HTMLElement | null;
    if (t && t.closest('input, textarea, select, [contenteditable="true"], [role="tablist"]')) return;
    if (e.key === 'ArrowLeft') { e.preventDefault(); navigatePrev(); }
    if (e.key === 'ArrowRight') { e.preventDefault(); navigateNext(); }
  }

  // Keyboard focus trap — keep Tab cycling inside the dialog (aria-modal handles AT).
  function trapTab(e: KeyboardEvent) {
    if (!modalEl) return;
    const focusables = Array.from(
      modalEl.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ),
    ).filter((el) => el.offsetParent !== null || el === document.activeElement);
    if (focusables.length === 0) { e.preventDefault(); modalEl.focus(); return; }
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    const active = document.activeElement;
    if (e.shiftKey && (active === first || active === modalEl)) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && active === last) {
      e.preventDefault();
      first.focus();
    }
  }

  function handleBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget) {
      onClose();
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- Click-popover content: methodology ("what it measures") + this idea's reasoning. -->
{#snippet scoreDetail(def: string, why: string | null, value: number | null | undefined)}
  <div class="space-y-3">
    <div>
      <div class="text-[10px] font-semibold uppercase tracking-wide text-text-muted mb-1">What this measures</div>
      <p class="text-text-secondary">{def}</p>
    </div>
    <div>
      <div class="text-[10px] font-semibold uppercase tracking-wide text-text-muted mb-1">Why this idea{value != null ? ` scored ${Math.round(value * 100)}` : ''}</div>
      <p class="text-text-secondary">{why || 'No idea-specific detail available yet.'}</p>
    </div>
  </div>
{/snippet}

{#if open}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div
    use:portal
    class="detail-backdrop"
    onclick={handleBackdropClick}
    role="dialog"
    aria-modal="true"
    aria-label="Solution details: {displayTitle}"
    tabindex="-1"
  >
    <!-- Modal card -->
    <div
      bind:this={modalEl}
      class="modal-card"
      tabindex="-1"
    >
      <!-- Header -->
      <div class="modal-header">
        <div class="modal-title-group">
          <span class="modal-kicker">Candidate {currentIndex + 1} of {total}</span>
          <h2 class="modal-title">{displayTitle}</h2>
          {#if hasHeadline}
            <p class="modal-subtitle">{solution.solution_name}</p>
          {/if}
          <div class="modal-meta">
            <Popover position="bottom" label="Overall score details">
              {#snippet trigger()}
                <div class="score-token">
                  <span class="score-dot" style:background={scoreColor} aria-hidden="true"></span>
                  <span style:color={scoreColor}>{Math.round(compositeScore * 100)}</span>
                </div>
              {/snippet}
              {@render scoreDetail(SCORE_DEFINITIONS.composite, compositeWhy, compositeScore)}
            </Popover>
            {#if superpower}
              <Badge variant={superpower.variant} size="sm">{superpower.label}</Badge>
            {/if}
          </div>
        </div>
        <div class="modal-actions">
          {#if total > 1}
            <div class="modal-nav" role="group" aria-label="Navigate ideas">
              <button
                type="button"
                class="modal-nav-btn"
                onclick={navigatePrev}
                aria-label="Previous idea"
              >
                <ChevronLeft class="w-4 h-4" />
              </button>
              <span class="modal-position">{currentIndex + 1} of {total}</span>
              <button
                type="button"
                class="modal-nav-btn"
                onclick={navigateNext}
                aria-label="Next idea"
              >
                <ChevronRight class="w-4 h-4" />
              </button>
            </div>
          {/if}
          {#if !onSelect && actionSlot}
            {@render actionSlot()}
          {/if}
          <!-- Close button -->
          <button
            type="button"
            onclick={onClose}
            aria-label="Close details"
            class="modal-close"
          >
            <X class="w-5 h-5" />
          </button>
        </div>
      </div>

      <!-- Tab bar: decision snapshot vs deep reference -->
      <div class="modal-tabs" role="tablist" aria-label="Idea detail views">
        <button
          type="button"
          role="tab"
          id="idea-tab-overview"
          aria-selected={activeTab === "overview"}
          aria-controls="idea-tabpanel"
          class="modal-tab"
          class:is-active={activeTab === "overview"}
          onclick={() => setTab("overview")}
        >Overview</button>
        <button
          type="button"
          role="tab"
          id="idea-tab-detail"
          aria-selected={activeTab === "detail"}
          aria-controls="idea-tabpanel"
          class="modal-tab"
          class:is-active={activeTab === "detail"}
          onclick={() => setTab("detail")}
        >Full detail</button>
      </div>

      <!-- Scrollable body -->
      <div
        class="modal-body"
        id="idea-tabpanel"
        role="tabpanel"
        tabindex="0"
        bind:this={bodyEl}
        aria-labelledby={activeTab === "overview" ? "idea-tab-overview" : "idea-tab-detail"}
      >
        {#if activeTab === "overview"}
        <section class="modal-score-panel" aria-label="Ranking rationale">
          <div class="score-panel-summary">
            <span class="score-panel-label">Decision rationale</span>
            <p>{compositeWhy || 'No idea-specific score rationale available yet.'}</p>
            {#if voteCount > 0}
              <span class="score-votes">{voteCount} community vote{voteCount === 1 ? '' : 's'}</span>
            {/if}
          </div>
          <div class="score-grid" aria-label="Score breakdown">
            {#each individualScores as s}
              <Popover position="bottom" label={`${s.label} score details`} class="score-popover-trigger">
                {#snippet trigger()}
                  <span class="score-item" title={s.def}>
                    <span class="score-item-label">{s.label}</span>
                    <span class="score-item-value" style:color={individualScoreColor(s.value)}>{s.value != null ? (s.value * 100).toFixed(0) : '--'}</span>
                  </span>
                {/snippet}
                {@render scoreDetail(s.def, s.why, s.value)}
              </Popover>
            {/each}
          </div>
        </section>
        <SolutionDetailContent
          {solution}
          view="overview"
          onViewFull={() => { setTab("detail"); document.getElementById("idea-tab-detail")?.focus(); }}
        />
        {:else}
        <SolutionDetailContent {solution} view="detail" />
        {/if}
      </div>

      <!-- Sticky footer select CTA -->
      {#if onSelect}
        <div class="modal-footer">
          <div class="modal-footer-status">
            <strong>{shortlistStatus}</strong>
            {#if startCost != null}
              <span>{startCost} credits / one-time</span>
            {/if}
            {#if maxReached && !isSelected}
              <span class="modal-footer-note">Remove one to add this candidate.</span>
            {/if}
          </div>
          <div class="modal-footer-actions">
            <button
              type="button"
              onclick={handleSelect}
              disabled={!isToggleable}
              title={maxReached && !isSelected ? 'Maximum 3 candidates shortlisted' : undefined}
              class="modal-select-primary"
              class:is-selected={isSelected}
            >
              <span class="select-indicator">
                {#if isSelected && selectionIndex}{selectionIndex}{/if}
              </span>
              {#if isSelected}
                Remove
              {:else if maxReached}
                Limit reached
              {:else}
                Shortlist
              {/if}
            </button>
            {#if onStartValidation}
              <button
                type="button"
                class="modal-start-primary"
                onclick={handleStartValidation}
                disabled={!canStart || disabled || starting}
                aria-busy={starting}
              >
                {starting ? "Starting…" : startLabel}
              </button>
            {/if}
          </div>
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .detail-backdrop {
    position: fixed;
    inset: 0;
    z-index: 50;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: clamp(0.75rem, 2vw, 1.5rem);
    background: color-mix(in srgb, var(--color-bg-base) 90%, transparent);
    backdrop-filter: blur(2px);
  }

  .modal-card {
    position: relative;
    z-index: 1;
    display: flex;
    flex-direction: column;
    width: min(54rem, calc(100vw - 1.5rem));
    max-height: min(88vh, 48rem);
    overflow: hidden;
    background: var(--color-bg-elevated);
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 78%, transparent);
    border-radius: 0.75rem;
    box-shadow: var(--shadow-lg);
  }

  .modal-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1.25rem;
    padding: 1rem 1rem 0.875rem;
    border-bottom: 1px solid var(--color-border);
    background: color-mix(in srgb, var(--color-bg-elevated) 94%, var(--color-bg-surface));
    flex-shrink: 0;
  }

  .modal-title-group {
    min-width: 0;
    flex: 1;
  }

  .modal-title {
    margin: 0;
    max-width: 31ch;
    font-family: var(--font-display);
    font-size: clamp(1.125rem, 1.45vw, 1.375rem);
    font-weight: 800;
    line-height: 1.12;
    letter-spacing: 0;
    color: var(--color-text-primary);
    text-wrap: balance;
  }

  .modal-kicker {
    display: block;
    margin-bottom: 0.25rem;
    color: var(--color-text-muted);
    font-size: 0.6875rem;
    font-weight: 700;
  }

  .modal-subtitle {
    margin: 0.125rem 0 0;
    font-family: var(--font-mono);
    font-size: 0.625rem;
    color: var(--color-text-muted);
  }

  .modal-meta {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-top: 0.5rem;
    flex-wrap: wrap;
    color: var(--color-text-muted);
    font-size: 0.75rem;
  }

  .score-token {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    min-height: 1.45rem;
    padding: 0.125rem 0.5rem 0.125rem 0.375rem;
    border: 1px solid color-mix(in srgb, var(--color-border) 72%, transparent);
    border-radius: 999px;
    background: color-mix(in srgb, var(--color-bg-surface) 58%, transparent);
    font-family: var(--font-mono);
    font-size: 0.8125rem;
    font-weight: 800;
    transition: border-color 0.15s ease, background 0.15s ease;
  }

  /* The composite-score token is a Popover trigger — signal it's clickable on hover/focus. */
  .modal-meta :global(.popover-trigger:hover .score-token),
  .modal-meta :global(.popover-trigger:focus-visible .score-token) {
    border-color: var(--color-border-emphasis);
    background: var(--color-bg-surface);
  }

  .score-dot {
    width: 0.48rem;
    height: 0.48rem;
    border-radius: 50%;
  }

  .modal-actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-shrink: 0;
  }

  .modal-nav {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.25rem;
    background: color-mix(in srgb, var(--color-bg-surface) 78%, var(--color-bg-elevated));
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 72%, transparent);
    border-radius: 0.625rem;
  }

  .modal-nav-btn {
    display: grid;
    place-items: center;
    width: 1.72rem;
    height: 1.72rem;
    border: 0;
    border-radius: 0.5rem;
    background: transparent;
    color: var(--color-text-muted);
    cursor: pointer;
    transition:      background 220ms cubic-bezier(0.32, 0.72, 0, 1),
      color 220ms cubic-bezier(0.32, 0.72, 0, 1);
  }

  .modal-nav-btn:hover {    background: var(--color-bg-elevated);
    color: var(--color-text-primary);
  }

  .modal-position {
    padding: 0 0.25rem;
    font-size: 0.75rem;
    color: var(--color-text-muted);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }

  .modal-select-primary {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    border: 1px solid var(--color-border-emphasis);
    background: var(--color-bg-elevated);
    color: var(--color-text-secondary);
    cursor: pointer;
    font-weight: 700;
    transition:
      border-color 220ms cubic-bezier(0.32, 0.72, 0, 1),
      color 220ms cubic-bezier(0.32, 0.72, 0, 1),
      background 220ms cubic-bezier(0.32, 0.72, 0, 1);
  }

  .modal-select-primary {
    min-height: 2.36rem;
    padding: 0.5rem 0.875rem;
    border-radius: 0.625rem;
    font-size: 0.8125rem;
  }

  .modal-select-primary:hover:not(:disabled) {
    border-color: var(--color-accent);
    background: color-mix(in srgb, var(--color-accent) 5%, var(--color-bg-elevated));
    color: var(--color-accent-dark);
  }

  /* Shortlisted = a positive filled state, clearly distinct from the un-selected button. */
  .modal-select-primary.is-selected {
    color: var(--color-accent-dark);
    background: var(--color-accent-subtle);
    border-color: color-mix(in srgb, var(--color-accent) 40%, var(--color-border));
  }

  .modal-select-primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .select-indicator {
    display: grid;
    place-items: center;
    width: 1.16rem;
    height: 1.16rem;
    border-radius: 0.375rem;
    border: 1.5px solid currentColor;
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 800;
    line-height: 1;
  }

  .is-selected .select-indicator {
    background: transparent;
    border-color: currentColor;
    color: inherit;
  }

  .modal-close {
    display: grid;
    place-items: center;
    width: 2.25rem;
    height: 2.25rem;
    border: 1px solid transparent;
    border-radius: 0.625rem;
    background: transparent;
    color: var(--color-text-muted);
    cursor: pointer;
    transition:      background 220ms cubic-bezier(0.32, 0.72, 0, 1),
      color 220ms cubic-bezier(0.32, 0.72, 0, 1);
  }

  .modal-close:hover {    background: var(--color-bg-surface);
    color: var(--color-text-primary);
  }

  .modal-select-primary:focus-visible,
  .modal-start-primary:focus-visible,
  .modal-close:focus-visible,
  .modal-nav-btn:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .modal-tabs {
    display: flex;
    gap: 0.25rem;
    flex-shrink: 0;
    padding: 0 1rem;
    background: var(--color-bg-elevated);
    border-bottom: 1px solid var(--color-border);
  }

  .modal-tab {
    position: relative;
    padding: 0.625rem 0.25rem;
    margin-right: 1.125rem;
    border: 0;
    background: transparent;
    color: var(--color-text-muted);
    font-family: var(--font-body);
    font-size: 0.8125rem;
    font-weight: 700;
    cursor: pointer;
    transition: color 0.15s ease;
  }

  .modal-tab::after {
    content: "";
    position: absolute;
    left: 0;
    right: 0;
    bottom: -1px;
    height: 2px;
    background: var(--color-accent);
    opacity: 0;
    transition: opacity 0.15s ease;
  }

  .modal-tab:hover {
    color: var(--color-text-secondary);
  }

  .modal-tab.is-active {
    color: var(--color-text-primary);
  }

  .modal-tab.is-active::after {
    opacity: 1;
  }

  .modal-tab:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
    border-radius: 0.25rem;
  }

  .modal-body {
    flex: 1;
    display: grid;
    gap: 0.875rem;
    align-content: start;
    min-height: 0;
    overflow-y: auto;
    padding: 0.875rem 1rem 1rem;
    background: color-mix(in srgb, var(--color-bg-elevated) 96%, var(--color-bg-surface));
  }

  .modal-score-panel {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 0.875rem;
    align-items: center;
    padding: 0.625rem;
    background: color-mix(in srgb, var(--color-bg-surface) 46%, var(--color-bg-elevated));
    border: 1px solid color-mix(in srgb, var(--color-border) 78%, transparent);
    border-radius: 0.625rem;
  }

  .score-panel-summary {
    min-width: 0;
  }

  .score-panel-label,
  .score-item-label {
    display: block;
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 700;
    color: var(--color-text-muted);
  }

  .score-panel-summary p {
    margin: 0.25rem 0 0;
    color: var(--color-text-secondary);
    font-size: 0.75rem;
    line-height: 1.42;
    text-wrap: pretty;
  }

  .score-votes {
    display: inline-flex;
    margin-top: 0.5rem;
    color: var(--color-text-secondary);
    font-size: 0.75rem;
    font-weight: 600;
  }

  .score-grid {
    display: grid;
    grid-template-columns: repeat(5, minmax(3.42rem, 1fr));
    justify-content: flex-end;
    gap: 0.25rem;
    align-self: start;
    overflow: visible;
    border: 0;
    border-radius: 0;
  }

  .score-item {
    display: grid;
    gap: 0.125rem;
    min-width: 0;
    width: 100%;
    min-height: 3.1rem;
    padding: 0.375rem 0.5rem;
    background: color-mix(in srgb, var(--color-bg-elevated) 84%, var(--color-bg-surface));
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 62%, transparent);
    border-radius: 0.5rem;
    transition:
      border-color 220ms cubic-bezier(0.32, 0.72, 0, 1),
      background 220ms cubic-bezier(0.32, 0.72, 0, 1);
  }

  .score-grid :global(.popover-trigger.score-popover-trigger) {
    display: block;
    width: 100%;
    color: inherit;
    text-align: left;
  }

  .score-grid :global(.popover-trigger.score-popover-trigger:hover) {
    opacity: 1;
  }

  .score-item:hover {
    border-color: var(--color-border-emphasis);
    background: var(--color-bg-elevated);
  }

  .score-grid :global(.popover-trigger.score-popover-trigger:focus-visible) {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
    border-radius: 0.5rem;
  }

  .score-item-value {
    font-family: var(--font-mono);
    font-size: 0.875rem;
    font-weight: 800;
    line-height: 1;
    font-variant-numeric: tabular-nums;
  }

  .modal-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    flex-shrink: 0;
    padding: 0.625rem 1rem;
    border-top: 1px solid var(--color-border);
    background: color-mix(in srgb, var(--color-bg-surface) 72%, var(--color-bg-elevated));
  }

  .modal-footer-status {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 0.25rem 0.5rem;
    min-width: 0;
    color: var(--color-text-muted);
    font-size: 0.75rem;
    line-height: 1.35;
  }

  .modal-footer-status strong {
    font-family: var(--font-mono);
    color: var(--color-text-primary);
    font-size: 0.8125rem;
    font-weight: 800;
    font-variant-numeric: tabular-nums;
  }

  .modal-footer-note {
    color: var(--color-warning-dark);
  }

  .modal-footer-actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-shrink: 0;
  }

  .modal-start-primary {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 2.36rem;
    padding: 0.5rem 1rem;
    border: 1px solid var(--color-accent-hover);
    border-radius: 0.625rem;
    background: var(--color-accent-hover);
    color: white;
    font-size: 0.8125rem;
    font-weight: 800;
    cursor: pointer;
    transition:      border-color 220ms cubic-bezier(0.32, 0.72, 0, 1),
      background 220ms cubic-bezier(0.32, 0.72, 0, 1),
      color 220ms cubic-bezier(0.32, 0.72, 0, 1);
  }

  .modal-start-primary:hover:not(:disabled) {
    border-color: var(--color-accent-dark);
    background: var(--color-accent-dark);
  }

  .modal-start-primary:disabled {
    border-color: var(--color-border);
    background: color-mix(in srgb, var(--color-bg-surface) 82%, var(--color-bg-elevated));
    color: var(--color-text-muted);
    cursor: not-allowed;
  }

  /* On smaller screens, position arrows at edge */
  @media (max-width: 900px) {
    .modal-card {
      max-height: 92vh;
      border-radius: 0.75rem;
    }
    .modal-header {
      flex-direction: column;
      padding: 1rem;
    }
    .modal-actions {
      width: 100%;
      justify-content: space-between;
      flex-wrap: wrap;
    }
    .modal-body {
      padding: 1rem;
    }
    .modal-score-panel {
      grid-template-columns: 1fr;
    }
    .score-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
      justify-content: stretch;
    }
    .modal-footer {
      align-items: stretch;
      flex-direction: column;
      padding: 0.75rem 1rem;
    }
    .modal-footer-actions {
      width: 100%;
    }
    .modal-select-primary,
    .modal-start-primary {
      flex: 1;
    }
  }

  /* Hide arrows on very small screens (use keyboard/swipe instead) */
  @media (max-width: 480px) {
    .modal-title {
      font-size: 1.25rem;
    }
    .modal-select-primary {
      width: 100%;
    }
    .modal-footer-actions {
      flex-direction: column;
    }
    .modal-start-primary {
      width: 100%;
    }
  }
</style>
