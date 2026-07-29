<script lang="ts">
  import type { Snippet } from "svelte";
  import { untrack } from "svelte";
  import {
    Check,
    ChevronLeft,
    ChevronRight,
    Download,
    Plus,
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
  // across paging so a user comparing All details isn't bounced back to Decision summary;
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
        const matches = solutions
          .map((candidate, index) => ({ candidate, index }))
          .filter(({ candidate }) => candidate.solution_name === name);
        const match = matches.length === 1 ? matches[0] : null;
        return {
          title: match ? solutionDisplayTitle(match.candidate) : name,
          index: match?.index ?? null,
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
  <div class="score-detail">
    <div class="score-detail-section">
      <span class="score-detail-label">What this measures</span>
      <p>{def}</p>
    </div>
    <div class="score-detail-section">
      <span class="score-detail-label">Why this idea{value != null ? ` scored ${Math.round(value * 100)}` : ''}</span>
      <p>{why || 'No idea-specific detail available yet.'}</p>
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
          <span class="modal-kicker">Candidate detail</span>
          <h2 class="modal-title" data-annotation-anchor="solution-header-title">{displayTitle}</h2>
          {#if showWorkingName}
            <p class="modal-subtitle" title="The internal working name for this candidate">
              <span class="modal-subtitle-kicker">Working name</span>
              {solution.solution_name}
            </p>
          {/if}
          <div class="modal-meta">
            <Popover position="bottom" label="Discovery score details">
              {#snippet trigger()}
                <div class="score-token">
                  <span class="score-token-label">Discovery score</span>
                  <span class="score-token-value" style:color={scoreColor}>
                    {compositeScore === null ? "Not scored" : Math.round(compositeScore * 100)}
                  </span>
                  {#if compositeScore !== null}
                    <span class="score-token-scale">/ 100</span>
                  {/if}
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
                aria-label="Download Markdown"
                title="Download the full stored candidate record as Markdown"
              >
                <Download class="w-4 h-4" aria-hidden="true" />
                <span>MD</span>
              </a>
              <a
                class="modal-export-link"
                href="{exportBase}/json?revision={exportRevision}"
                download
                aria-label="Download JSON"
                title="Download the full stored candidate record as JSON"
              >
                <Download class="w-4 h-4" aria-hidden="true" />
                <span>JSON</span>
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
        >Decision summary</button>
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
        >All details</button>
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
          onViewFull={() => { setTab("detail"); detailTabEl?.focus(); }}
        />
        {:else}
        <SolutionDetailContent {solution} view="detail" {lifecycle} {evidenceLinks} {onOpenEvidence} />
        {/if}
      </div>

      <!-- Sticky footer select CTA -->
      {#if lifecycle === "selection" && onSelect}
        <div class="modal-footer" data-annotation-anchor="solution-footer">
          <div class="modal-footer-status">
            <span class="modal-footer-label">Research shortlist</span>
            <strong>{selectedCount} of {maxSelections}</strong>
            {#if maxReached && !isSelected}
              <span class="modal-footer-note" id="shortlist-limit-note">
                Shortlist is full. Remove another candidate first.
              </span>
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
              <span class="select-indicator" aria-hidden="true">
                {#if isSelected}
                  <Check class="w-4 h-4" />
                {:else}
                  <Plus class="w-4 h-4" />
                {/if}
              </span>
              {#if isSelected && selectionIndex}
                <span class="sr-only">Shortlist position {selectionIndex}.</span>
              {/if}
              {#if isSelected}
                Remove from shortlist
              {:else if maxReached}
                Shortlist full
              {:else}
                Add to shortlist
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
    gap: var(--space-5);
    padding: var(--space-5) var(--space-5) var(--space-4);
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
    max-width: 34ch;
    font-family: var(--font-display);
    font-size: var(--text-2xl);
    font-weight: 800;
    line-height: var(--leading-tight);
    letter-spacing: 0;
    color: var(--color-text-primary);
    text-wrap: balance;
    overflow-wrap: anywhere;
  }

  .modal-kicker {
    display: block;
    margin-bottom: var(--space-1);
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: var(--tracking-wide);
    text-transform: uppercase;
  }

  .modal-subtitle {
    margin: var(--space-1) 0 0;
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--color-text-muted);
    overflow-wrap: anywhere;
  }

  .modal-subtitle-kicker {
    margin-right: var(--space-1);
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }

  .modal-meta {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-top: var(--space-3);
    flex-wrap: wrap;
    color: var(--color-text-muted);
    font-size: var(--text-sm);
  }

  .score-token {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    min-height: var(--space-8);
    padding: var(--space-1) var(--space-2);
    border: 1px solid color-mix(in srgb, var(--color-border) 72%, transparent);
    border-radius: var(--radius-full);
    background: color-mix(in srgb, var(--color-bg-surface) 58%, transparent);
    font-family: var(--font-mono);
    transition:
      border-color var(--duration-normal) var(--ease-out),
      background var(--duration-normal) var(--ease-out);
  }

  /* The composite-score token is a Popover trigger — signal it's clickable on hover/focus. */
  .modal-meta :global(.popover-trigger:hover .score-token),
  .modal-meta :global(.popover-trigger:focus-visible .score-token) {
    border-color: var(--color-border-emphasis);
    background: var(--color-bg-surface);
  }

  .score-token-label {
    color: var(--color-text-muted);
    font-size: var(--text-xs);
    font-weight: 600;
  }

  .score-token-value {
    color: var(--color-text-primary);
    font-size: var(--text-sm);
    font-weight: 800;
    font-variant-numeric: tabular-nums;
  }

  .score-token-scale {
    color: var(--color-text-muted);
    font-size: var(--text-xs);
    font-weight: 500;
  }

  .score-detail {
    display: grid;
    gap: var(--space-4);
    max-width: 42ch;
  }

  .score-detail-section {
    display: grid;
    gap: var(--space-1);
  }

  .score-detail-label {
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: var(--tracking-wide);
    text-transform: uppercase;
  }

  .score-detail p {
    margin: 0;
    color: var(--color-text-secondary);
    font-size: var(--text-base);
    line-height: var(--leading-normal);
  }

  .modal-actions {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-shrink: 0;
  }

  .modal-nav,
  .modal-export {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    padding: var(--space-1);
    background: color-mix(in srgb, var(--color-bg-surface) 78%, var(--color-bg-elevated));
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 72%, transparent);
    border-radius: var(--radius-lg);
  }

  .modal-nav-btn,
  .modal-close {
    display: grid;
    place-items: center;
    width: var(--space-10);
    height: var(--space-10);
    border: 1px solid transparent;
    border-radius: var(--radius-md);
    background: transparent;
    color: var(--color-text-muted);
    cursor: pointer;
    transition:
      background var(--duration-normal) var(--ease-out),
      border-color var(--duration-normal) var(--ease-out),
      color var(--duration-normal) var(--ease-out);
  }

  .modal-nav-btn:hover,
  .modal-close:hover {
    border-color: var(--color-border);
    background: var(--color-bg-elevated);
    color: var(--color-text-primary);
  }

  .modal-position {
    padding: 0 var(--space-1);
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }

  .modal-export-link {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    min-height: var(--space-10);
    padding: 0 var(--space-2);
    border-radius: var(--radius-md);
    background: transparent;
    color: var(--color-text-muted);
    font-size: var(--text-sm);
    font-weight: 700;
    text-decoration: none;
    transition:
      background var(--duration-normal) var(--ease-out),
      color var(--duration-normal) var(--ease-out);
  }

  .modal-export-link:hover {
    background: var(--color-bg-elevated);
    color: var(--color-text-primary);
  }

  .modal-select-primary {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    min-height: var(--space-10);
    padding: var(--space-2) var(--space-4);
    border: 1px solid var(--color-accent-hover);
    border-radius: var(--radius-md);
    background: var(--color-accent-hover);
    color: var(--color-text-on-accent);
    cursor: pointer;
    font-size: var(--text-sm);
    font-weight: 700;
    transition:
      background var(--duration-normal) var(--ease-out),
      border-color var(--duration-normal) var(--ease-out),
      color var(--duration-normal) var(--ease-out);
  }

  .modal-select-primary:hover:not(:disabled):not(.is-selected) {
    border-color: var(--color-accent-dark);
    background: var(--color-accent-dark);
  }

  .modal-select-primary.is-selected {
    border-color: var(--color-border-emphasis);
    background: var(--color-bg-elevated);
    color: var(--color-text-secondary);
  }

  .modal-select-primary.is-selected:hover:not(:disabled) {
    border-color: var(--color-text-secondary);
    background: var(--color-bg-surface);
    color: var(--color-text-primary);
  }

  .modal-select-primary:disabled {
    border-color: var(--color-border);
    background: var(--color-bg-surface);
    color: var(--color-text-muted);
    cursor: not-allowed;
    opacity: var(--opacity-disabled);
  }

  .select-indicator {
    display: grid;
    place-items: center;
    width: var(--space-5);
    height: var(--space-5);
    border: 1px solid currentColor;
    border-radius: var(--radius-sm);
    flex-shrink: 0;
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
    gap: var(--space-1);
    flex-shrink: 0;
    padding: 0 var(--space-5);
    background: var(--color-bg-elevated);
    border-bottom: 1px solid var(--color-border);
  }

  .modal-tab {
    position: relative;
    min-height: var(--space-10);
    margin-right: var(--space-4);
    padding: var(--space-2) var(--space-1);
    border: 0;
    background: transparent;
    color: var(--color-text-muted);
    cursor: pointer;
    font-family: var(--font-body);
    font-size: var(--text-sm);
    font-weight: 700;
    transition: color var(--duration-normal) var(--ease-out);
  }

  .modal-tab::after {
    content: "";
    position: absolute;
    right: 0;
    bottom: -1px;
    left: 0;
    height: 2px;
    background: var(--color-accent);
    opacity: 0;
    transition: opacity var(--duration-normal) var(--ease-out);
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
    border-radius: var(--radius-sm);
  }

  .modal-body {
    flex: 1;
    display: grid;
    gap: var(--space-4);
    align-content: start;
    min-height: 0;
    overflow-y: auto;
    padding: var(--space-4) var(--space-5) var(--space-5);
    background: color-mix(in srgb, var(--color-bg-elevated) 96%, var(--color-bg-surface));
  }

  .modal-score-panel {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: var(--space-4);
    align-items: center;
    padding: var(--space-3);
    background: color-mix(in srgb, var(--color-bg-surface) 46%, var(--color-bg-elevated));
    border: 1px solid color-mix(in srgb, var(--color-border) 78%, transparent);
    border-radius: var(--radius-lg);
  }

  .score-panel-summary {
    min-width: 0;
  }

  .score-panel-label,
  .score-item-label {
    display: block;
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: var(--tracking-wide);
    text-transform: uppercase;
  }

  .score-panel-summary p {
    max-width: 68ch;
    margin: var(--space-1) 0 0;
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: var(--leading-normal);
    overflow-wrap: anywhere;
    text-wrap: pretty;
  }

  .score-votes {
    display: inline-flex;
    margin-top: var(--space-2);
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    font-weight: 600;
  }

  .score-grid {
    display: grid;
    grid-template-columns: repeat(5, minmax(var(--space-20), 1fr));
    gap: var(--space-1);
    align-self: start;
    justify-content: flex-end;
    overflow: visible;
    border: 0;
  }

  .score-item {
    display: grid;
    gap: var(--space-1);
    min-width: 0;
    min-height: var(--space-16);
    width: 100%;
    padding: var(--space-2);
    background: color-mix(in srgb, var(--color-bg-elevated) 84%, var(--color-bg-surface));
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 62%, transparent);
    border-radius: var(--radius-md);
    transition:
      background var(--duration-normal) var(--ease-out),
      border-color var(--duration-normal) var(--ease-out);
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
    border-radius: var(--radius-md);
  }

  .score-item-value {
    font-family: var(--font-mono);
    font-size: var(--text-base);
    font-weight: 800;
    line-height: var(--leading-tight);
    font-variant-numeric: tabular-nums;
  }

  .modal-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-4);
    flex-shrink: 0;
    padding: var(--space-3) var(--space-5);
    border-top: 1px solid var(--color-border);
    background: color-mix(in srgb, var(--color-bg-surface) 72%, var(--color-bg-elevated));
  }

  .modal-footer-status {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: var(--space-1) var(--space-2);
    min-width: 0;
    color: var(--color-text-muted);
    font-size: var(--text-sm);
    line-height: var(--leading-normal);
  }

  .modal-footer-label {
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: var(--tracking-wide);
    text-transform: uppercase;
  }

  .modal-footer-status strong {
    color: var(--color-text-primary);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
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
    gap: var(--space-2);
    flex-shrink: 0;
  }

  @media (max-width: 900px) {
    .modal-header {
      flex-direction: column;
      padding: var(--space-4);
    }

    .modal-actions {
      width: 100%;
      justify-content: flex-start;
      flex-wrap: wrap;
    }

    .modal-nav {
      margin-right: auto;
    }

    .modal-tabs {
      padding: 0 var(--space-4);
    }

    .modal-body {
      padding: var(--space-4);
    }

    .modal-score-panel {
      grid-template-columns: 1fr;
    }

    .score-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
      justify-content: stretch;
    }

    .modal-footer {
      align-items: flex-start;
      flex-direction: column;
    }

    .modal-footer-actions {
      width: 100%;
      justify-content: flex-end;
    }
  }

  @media (max-width: 480px) {
    .modal-header {
      padding: var(--space-3);
    }

    .modal-title {
      font-size: var(--text-2xl);
    }

    .modal-actions,
    .modal-export,
    .modal-select-primary {
      width: 100%;
    }

    .modal-export-link {
      flex: 1;
      justify-content: center;
    }

    .modal-tabs {
      overflow-x: auto;
      padding: 0 var(--space-3);
    }

    .modal-tab {
      flex: 0 0 auto;
    }

    .modal-body {
      padding: var(--space-3);
    }

    .score-grid {
      grid-template-columns: 1fr;
    }

    .modal-footer {
      padding: var(--space-3);
    }

    .modal-footer-actions,
    .modal-select-primary {
      width: 100%;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .modal-nav-btn,
    .modal-close,
    .modal-export-link,
    .modal-select-primary,
    .modal-tab,
    .modal-tab::after,
    .score-item {
      transition-duration: var(--duration-instant);
    }
  }
</style>
