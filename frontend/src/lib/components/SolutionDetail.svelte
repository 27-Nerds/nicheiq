<script lang="ts">
  import type { Snippet } from "svelte";
  import { untrack } from "svelte";
  import {
    ChevronLeft,
    ChevronRight,
    Download,
    X,
  } from "lucide-svelte";
  import Badge from "$lib/components/ui/Badge.svelte";
  import WorkspaceOverlay from "$lib/components/ui/WorkspaceOverlay.svelte";
  import SolutionDetailContent from "$lib/components/SolutionDetailContent.svelte";
  import AnnotationSurface from "$lib/components/annotations/AnnotationSurface.svelte";
  import Popover from "$lib/components/ui/Popover.svelte";
  import { scoreRationale } from "$lib/utils/scoreRationale";
  import { SCORE_DEFINITIONS } from "$lib/utils/scoreDefinitions";
  import type { SolutionPreview } from "$lib/types/job";
  import type { OverlapGroup } from "$lib/types/report";
  import { displayCompositeScore, solutionStrengthBadge, solutionDisplayTitle, originalityMetric } from "$lib/utils/solution-utils";

  type DetailTab = "overview" | "detail";
  type DetailLifecycle = "selection" | "reference" | "running" | "completed";

  interface Props {
    open: boolean;
    solution: SolutionPreview;
    solutions: SolutionPreview[];
    currentIndex: number;
    jobId?: string;
    isSelected?: boolean;
    disabled?: boolean;
    maxReached?: boolean;
    selectionIndex?: number;
    selectedCount?: number;
    maxSelections?: number;
    lifecycle?: DetailLifecycle;
    activeTab?: DetailTab;
    evidenceLinks?: { href: string; label: string }[];
    /** Surviving ideas identified as variants of the same underlying product (a merge was
     *  proposed but rejected). Used to flag, on the Overview tab, when the current candidate
     *  belongs to one of these groups. */
    overlapGroups?: OverlapGroup[];
    onSelect?: (solution: SolutionPreview) => void;
    onOpenEvidence?: (href: string) => void;
    onTabChange?: (tab: DetailTab) => void;
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
    jobId,
    isSelected = false,
    disabled = false,
    maxReached = false,
    selectionIndex = 0,
    selectedCount = 0,
    maxSelections = 3,
    lifecycle = "reference",
    activeTab: controlledTab,
    evidenceLinks = [],
    overlapGroups = [],
    onSelect,
    onOpenEvidence,
    onTabChange,
    onNavigate,
    onClose,
    actionSlot,
    voteCount = 0,
  }: Props = $props();

  let bodyEl: HTMLDivElement | undefined = $state();
  let overviewTabEl: HTMLButtonElement | undefined = $state();
  let detailTabEl: HTMLButtonElement | undefined = $state();

  // Overview = shortlist-decision snapshot; detail = the 7-card deep reference.
  let localTab = $state<DetailTab>("overview");
  const activeTab = $derived(controlledTab ?? localTab);
  const exactIdentity = $derived(
    solution.idea_id
      ? `${solution.idea_id}:${solution.idea_revision ?? 1}`
      : `legacy:${solution.solution_name}`,
  );

  // Scroll to top whenever the pager moves to another idea. The active tab is kept
  // across paging so a user comparing Full details isn't bounced back to Overview;
  // the sr-only live region above the header still announces the candidate change.
  $effect(() => {
    exactIdentity;
    untrack(() => {
      if (bodyEl) bodyEl.scrollTop = 0;
    });
  });

  function setTab(tab: DetailTab) {
    if (controlledTab === undefined) localTab = tab;
    onTabChange?.(tab);
    if (bodyEl) bodyEl.scrollTop = 0; // don't land mid-content when the view swaps
  }

  function handleTabKeydown(event: KeyboardEvent, current: DetailTab) {
    let next: DetailTab | null = null;
    if (event.key === "Home") next = "overview";
    if (event.key === "End") next = "detail";
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      next = current === "overview" ? "detail" : "overview";
    }
    if (!next) return;
    event.preventDefault();
    event.stopPropagation();
    setTab(next);
    (next === "overview" ? overviewTabEl : detailTabEl)?.focus();
  }

  const total = $derived(solutions.length);

  const compositeScore = $derived(displayCompositeScore(solution));
  const compositeWhy = $derived(scoreRationale(solution, "composite"));
  // Unclamped variant for the Decision rationale panel — a full-width surface, not a popover.
  const compositeWhyFull = $derived(scoreRationale(solution, "composite", { full: true }));

  // Score color (matches ProgressRing auto logic)
  const scoreColor = $derived.by(() => {
    if (compositeScore === null) return 'var(--color-text-muted)';
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
    { label: origMetric.short ?? "Distinct", value: origMetric.value, def: SCORE_DEFINITIONS.originality, why: scoreRationale(solution, "novelty") },
    { label: "Solo", value: solution.solo_dev_feasibility, def: SCORE_DEFINITIONS.solo_dev, why: scoreRationale(solution, "solo_dev") },
  ]);

  // Backend-sourced strength badge (tags.primary_strength); legacy fallback for pre-tags data.
  const superpower = $derived(solutionStrengthBadge(solution, true));

  const displayTitle = $derived(solutionDisplayTitle(solution));
  // The raw internal solution_name is a working name — only worth a subtitle when a
  // headline is shown as the title AND the working name isn't just the headline again.
  const showWorkingName = $derived(
    !!solution.headline?.trim() && solution.headline.trim() !== solution.solution_name,
  );

  // Overlap group this candidate belongs to, if the run's synthesis found one (a merge was
  // proposed but rejected, so the variants stay as separate shortlist entries).
  // Overlap reports predate stable idea references and contain names only. Apply one only
  // when the current name is unique; duplicate-name candidates must never inherit each
  // other's grouping by accident.
  const overlapGroup = $derived(
    solutions.filter((candidate) => candidate.solution_name === solution.solution_name).length === 1
      ? overlapGroups.find((group) => group.idea_names.includes(solution.solution_name)) ?? null
      : null,
  );

  // Overlap peers resolved against the current pool: overlap reports carry internal
  // solution_names, so map each to its candidate's display title and pool index (for
  // paging the overlay straight to it); names not in the pool keep index null.
  const overlapPeers = $derived.by(() => {
    if (!overlapGroup) return [];
    return overlapGroup.idea_names
      .filter((name) => name !== solution.solution_name)
      .map((name) => {
        const index = solutions.findIndex((candidate) => candidate.solution_name === name);
        return {
          title: index >= 0 ? solutionDisplayTitle(solutions[index]) : name,
          index: index >= 0 ? index : null,
        };
      });
  });

  const isToggleable = $derived(
    lifecycle === "selection" && !!onSelect && !disabled && (isSelected || !maxReached),
  );

  // Private export of the exact stored revision being viewed (full candidate record).
  const exportBase = $derived(
    jobId && solution.idea_id
      ? `/api/jobs/${jobId}/solutions/${solution.idea_id}/export`
      : null,
  );
  const exportRevision = $derived(solution.idea_revision ?? 1);
  const shortlistStatus = $derived(`${selectedCount}/${maxSelections} shortlisted`);

  function handleSelect() {
    if (!isToggleable || !onSelect) return;
    onSelect(solution);
  }

  function navigatePrev() {
    const prev = currentIndex <= 0 ? total - 1 : currentIndex - 1;
    onNavigate(prev);
  }

  function navigateNext() {
    const next = currentIndex >= total - 1 ? 0 : currentIndex + 1;
    onNavigate(next);
  }

  function handleOverlayKeydown(e: KeyboardEvent) {
    // Arrow paging only when focus isn't in a control that uses arrows itself
    // (form fields, or the tablist — where arrows belong to tab switching, not paging).
    const t = e.target as HTMLElement | null;
    if (
      e.defaultPrevented
      || e.altKey
      || e.ctrlKey
      || e.metaKey
      || e.shiftKey
      || (t && t.closest(
        'a, button, input, textarea, select, summary, [contenteditable="true"], '
        + '[role="button"], [role="link"], [role="menu"], [role="listbox"], '
        + '[role="option"], [role="tablist"], [data-no-idea-paging]',
      ))
    ) return;
    if (e.key === 'ArrowLeft') { e.preventDefault(); navigatePrev(); }
    if (e.key === 'ArrowRight') { e.preventDefault(); navigateNext(); }
  }

</script>

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

<WorkspaceOverlay
  {open}
  size="standard"
  label={`Solution details: ${displayTitle}`}
  onClose={onClose}
  onKeydown={handleOverlayKeydown}
>
    <!-- Modal card -->
    <div class="modal-card">
      <AnnotationSurface
        surfaceKey={`solution-detail:${exactIdentity}:${activeTab}`}
        anchorKey="solution-detail"
        class="modal-annotation-surface"
      >
      <!-- Header -->
      <div class="modal-header" data-annotation-anchor="solution-header">
        <p class="sr-only" aria-live="polite" aria-atomic="true">
          Viewing candidate {currentIndex + 1} of {total}: {displayTitle}, revision {exportRevision}.
        </p>
        <div class="modal-title-group" data-annotation-anchor="solution-header-copy">
          <span class="modal-kicker">Candidate {currentIndex + 1} of {total}</span>
          <h2 class="modal-title" data-annotation-anchor="solution-header-title">{displayTitle}</h2>
          {#if showWorkingName}
            <p class="modal-subtitle" title="The internal working name for this candidate">
              <span class="modal-subtitle-kicker">Working name</span>
              {solution.solution_name}
            </p>
          {/if}
          <div class="modal-meta">
            <Popover position="bottom" label="Overall score details">
              {#snippet trigger()}
                <div class="score-token">
                  {#if compositeScore !== null}
                    <span class="score-dot" style:background={scoreColor} aria-hidden="true"></span>
                  {/if}
                  <span style:color={scoreColor}>
                    {compositeScore === null ? "Not scored" : Math.round(compositeScore * 100)}
                  </span>
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
          {#if exportBase}
            <div class="modal-export" role="group" aria-label="Export this candidate">
              <a
                class="modal-export-link"
                href="{exportBase}/md?revision={exportRevision}"
                download
                title="Download the full stored candidate record as Markdown"
              >
                <Download class="w-4 h-4" aria-hidden="true" />
                <span>.md</span>
              </a>
              <a
                class="modal-export-link"
                href="{exportBase}/json?revision={exportRevision}"
                download
                title="Download the full stored candidate record as JSON"
              >
                <Download class="w-4 h-4" aria-hidden="true" />
                <span>.json</span>
              </a>
            </div>
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
      <div class="modal-tabs" role="tablist" aria-label="Idea detail views" data-annotation-anchor="solution-tabs">
        <button
          bind:this={overviewTabEl}
          type="button"
          role="tab"
          id="idea-tab-overview"
          aria-selected={activeTab === "overview"}
          aria-controls="idea-tabpanel"
          tabindex={activeTab === "overview" ? 0 : -1}
          class="modal-tab"
          class:is-active={activeTab === "overview"}
          onclick={() => setTab("overview")}
          onkeydown={(event) => handleTabKeydown(event, "overview")}
        >Overview</button>
        <button
          bind:this={detailTabEl}
          type="button"
          role="tab"
          id="idea-tab-detail"
          aria-selected={activeTab === "detail"}
          aria-controls="idea-tabpanel"
          tabindex={activeTab === "detail" ? 0 : -1}
          class="modal-tab"
          class:is-active={activeTab === "detail"}
          onclick={() => setTab("detail")}
          onkeydown={(event) => handleTabKeydown(event, "detail")}
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
        data-annotation-anchor={`solution-body:${activeTab}`}
      >
        {#if activeTab === "overview"}
        <section
          class="modal-score-panel"
          aria-label="Ranking rationale"
          data-annotation-anchor="solution-body:overview:score"
        >
          <div class="score-panel-summary">
            <span class="score-panel-label">Decision rationale</span>
            <p>{compositeWhyFull || 'No idea-specific score rationale available yet.'}</p>
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
          {overlapGroup}
          {overlapPeers}
          onOpenPeer={onNavigate}
          {lifecycle}
          {evidenceLinks}
          {onOpenEvidence}
          onViewFull={() => { setTab("detail"); document.getElementById("idea-tab-detail")?.focus(); }}
        />
        {:else}
        <SolutionDetailContent {solution} view="detail" {lifecycle} {evidenceLinks} {onOpenEvidence} />
        {/if}
      </div>

      <!-- Sticky footer select CTA -->
      {#if lifecycle === "selection" && onSelect}
        <div class="modal-footer" data-annotation-anchor="solution-footer">
          <div class="modal-footer-status">
            <strong>{shortlistStatus}</strong>
            {#if maxReached && !isSelected}
              <span class="modal-footer-note" id="shortlist-limit-note">Remove one to add this candidate.</span>
            {/if}
          </div>
          <div class="modal-footer-actions">
            <button
              type="button"
              onclick={handleSelect}
              disabled={!isToggleable}
              aria-describedby={maxReached && !isSelected ? 'shortlist-limit-note' : undefined}
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
          </div>
        </div>
      {/if}
      </AnnotationSurface>
    </div>
</WorkspaceOverlay>

<style>
  .modal-card {
    position: relative;
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 100%;
    overflow: hidden;
    background: var(--color-bg-elevated);
  }

  :global(.modal-annotation-surface) {
    display: flex;
    flex: 1;
    flex-direction: column;
    min-height: 0;
    height: 100%;
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
    overflow-wrap: anywhere;
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
    overflow-wrap: anywhere;
  }

  .modal-subtitle-kicker {
    margin-right: 0.25rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
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

  .modal-export {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.25rem;
    background: color-mix(in srgb, var(--color-bg-surface) 78%, var(--color-bg-elevated));
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 72%, transparent);
    border-radius: 0.625rem;
  }

  .modal-export-link {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    min-height: 1.72rem;
    padding: 0 0.4rem;
    border-radius: 0.5rem;
    background: transparent;
    color: var(--color-text-muted);
    font-size: 0.75rem;
    font-weight: 600;
    text-decoration: none;
    transition:
      background 220ms cubic-bezier(0.32, 0.72, 0, 1),
      color 220ms cubic-bezier(0.32, 0.72, 0, 1);
  }

  .modal-export-link:hover {
    background: var(--color-bg-elevated);
    color: var(--color-text-primary);
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
  .modal-close:focus-visible,
  .modal-nav-btn:focus-visible,
  .modal-export-link:focus-visible {
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
    overflow-wrap: anywhere;
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
    overflow-wrap: anywhere;
  }

  .modal-footer-actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-shrink: 0;
  }

  /* On smaller screens, position arrows at edge */
  @media (max-width: 900px) {
    .modal-header {
      flex-direction: column;
      padding: 1rem;
    }
    .modal-actions {
      width: 100%;
      justify-content: flex-start;
      flex-wrap: wrap;
    }
    .modal-nav {
      margin-right: auto;
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
    .modal-select-primary {
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
  }
</style>
