<script lang="ts">
  import { X } from "lucide-svelte";
  import { portal } from "$lib/actions/portal";
  import { REVIEW_AND_START_LABEL } from "$lib/selection/labels";
  import type { SelectionJourney } from "$lib/selection/decisionJourney";

  interface Props {
    journey: SelectionJourney;
    deepResearchCost?: number | null;
    busy?: boolean;
    busyReason?: string;
    saveState?: "idle" | "saving" | "saved" | "error";
    saveError?: string;
    saveConflict?: boolean;
    onRemoveShortlistItem?: (ideaId: string, ideaRevision: number) => void;
    onRetrySave: () => void;
    onReloadSave: () => void;
    onStartDeepResearch: () => void;
  }

  let {
    journey,
    deepResearchCost = null,
    busy = false,
    busyReason = "Another update is in progress. You can review the research scope when it finishes.",
    saveState = "idle",
    saveError = "",
    saveConflict = false,
    onRemoveShortlistItem,
    onRetrySave,
    onReloadSave,
    onStartDeepResearch,
  }: Props = $props();

  const shortlistCount = $derived(
    journey.shortlist.items.length + journey.shortlist.staleItems.length,
  );
  const canReview = $derived(
    journey.deepResearch.eligible
    && journey.shortlist.staleItems.length === 0
    && !busy,
  );
  const costLabel = $derived(
    deepResearchCost == null
      ? "Cost shown before research starts"
      : `${deepResearchCost} credit${deepResearchCost === 1 ? "" : "s"} total`,
  );
  const disabledReason = $derived(
    journey.shortlist.staleItems.length > 0
      ? "Replace unavailable candidate revisions before reviewing the research scope."
      : shortlistCount === 0
      ? "Select at least one idea to review the research scope."
      : busy
        ? busyReason
        : !journey.deepResearch.eligible
          ? "Resolve the shortlist issue before reviewing the research scope."
          : "",
  );
  // Publish the dock's measured height so bottom-anchored fixed overlays
  // (TourInvitation) can lift clear of it instead of covering it. The dock is centred
  // but spans nearly the full content width, so horizontal anchoring cannot avoid it.
  // offsetHeight (border box), not clientHeight: the dock has a 1px border top and
  // bottom, and the padding box excludes both — consumers would lift 2px short.
  let dockHeight = $state(0);
  $effect(() => {
    const root = document.documentElement;
    const previousScrollPaddingBottom = root.style.scrollPaddingBottom;
    root.style.setProperty("--decision-rail-height", `${dockHeight}px`);
    // The dock is itself inset --space-4 from the viewport bottom, so reserving only its
    // height parks scrolled-to content exactly ON its top edge — a row's pain line ended
    // up flush under it. Clear the inset too, and leave a gap.
    root.style.scrollPaddingBottom = `calc(${dockHeight}px + var(--space-8))`;
    return () => {
      root.style.removeProperty("--decision-rail-height");
      if (previousScrollPaddingBottom) {
        root.style.scrollPaddingBottom = previousScrollPaddingBottom;
      } else {
        root.style.removeProperty("scroll-padding-bottom");
      }
    };
  });
</script>

<aside
  use:portal
  class="decision-dock"
  aria-label="Ideas for Deep Research"
  bind:offsetHeight={dockHeight}
>
  <div class="dock-count" aria-live="polite" aria-label={`${shortlistCount} of ${journey.shortlist.maxItems} ideas selected`}>
    <strong>{shortlistCount}</strong>
    <span>/ {journey.shortlist.maxItems}</span>
    <small>selected</small>
  </div>

  <span class="dock-rule" aria-hidden="true"></span>

  <div class="dock-scope">
    {#if shortlistCount > 0}
      <ul aria-label="Selected ideas">
        {#each journey.shortlist.items as idea (`${idea.ideaId}:${idea.ideaRevision}`)}
          <li data-idea-id={idea.ideaId} data-idea-revision={idea.ideaRevision}>
            <span title={idea.title}>{idea.title}</span>
            <button
              type="button"
              aria-label={`Remove ${idea.title} from shortlist`}
              disabled={busy || !onRemoveShortlistItem}
              onclick={() => onRemoveShortlistItem?.(idea.ideaId, idea.ideaRevision)}
            >
              <X aria-hidden="true" />
            </button>
          </li>
        {/each}
        {#each journey.shortlist.staleItems as idea (`stale:${idea.ideaId}:${idea.ideaRevision}`)}
          <li class="stale" data-idea-id={idea.ideaId} data-idea-revision={idea.ideaRevision}>
            <span title={idea.title || "Unavailable candidate revision"}>
              {idea.title || "Unavailable candidate"} · revision {idea.ideaRevision}
            </span>
            <small>Needs replacement</small>
          </li>
        {/each}
      </ul>
    {:else}
      <p>Select 1–3 ideas to continue.</p>
    {/if}

    {#if saveState === "saving"}
      <p class="save-state" role="status">Saving shortlist…</p>
    {:else if saveState === "saved"}
      <span class="sr-only" role="status">Shortlist saved</span>
    {:else if saveState === "error"}
      <div class="save-state save-state--error" role="alert">
        <span>{saveError || "Shortlist not saved."}</span>
        <button type="button" onclick={saveConflict ? onReloadSave : onRetrySave}>
          {saveConflict ? "Reload" : "Retry"}
        </button>
      </div>
    {/if}
  </div>

  <div class="dock-commit">
    <span class="dock-cost">{costLabel}</span>
    {#if disabledReason}<span id="review-scope-reason" class="dock-reason">{disabledReason}</span>{/if}
  </div>

  <button
    type="button"
    class="review-action"
    disabled={!canReview}
    aria-describedby={disabledReason ? "review-scope-reason" : undefined}
    onclick={onStartDeepResearch}
  >
    {REVIEW_AND_START_LABEL}
  </button>
</aside>

<style>
  .decision-dock {
    position: fixed;
    left: 50%;
    bottom: var(--space-4);
    z-index: var(--z-dropdown);
    display: grid;
    grid-template-columns: auto auto minmax(0, 1fr) auto auto;
    gap: var(--space-4);
    align-items: center;
    box-sizing: border-box;
    width: min(calc(100vw - var(--space-12)), 75rem);
    min-height: 3.5rem;
    padding: var(--space-2) var(--space-2) var(--space-2) var(--space-4);
    border: 1px solid var(--color-border-emphasis);
    border-radius: var(--radius-lg);
    background: var(--color-bg-elevated);
    box-shadow: var(--shadow-md);
    color: var(--color-text-primary);
    transform: translateX(-50%);
  }

  .dock-count {
    display: flex;
    align-items: baseline;
    gap: var(--space-1);
    min-width: max-content;
    font-family: var(--font-mono);
    font-size: var(--text-11);
    font-variant-numeric: tabular-nums;
    font-feature-settings: "zero" 0;
  }

  .dock-count strong {
    font-size: var(--text-xl);
    font-weight: 700;
    line-height: 1;
  }

  .dock-count span,
  .dock-count small {
    color: var(--color-text-muted);
    font-size: var(--text-11);
    font-weight: 600;
  }

  .dock-rule {
    width: 1px;
    align-self: stretch;
    background: var(--color-border);
  }

  .dock-scope {
    min-width: 0;
  }

  .dock-scope ul {
    display: flex;
    gap: var(--space-2);
    min-width: 0;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .dock-scope li {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: var(--space-1);
    align-items: center;
    min-width: 0;
    max-width: 14rem;
    padding: var(--space-1) var(--space-1) var(--space-1) var(--space-2);
    border: 1px solid var(--color-border-accent);
    border-radius: var(--radius-md);
    background: var(--color-bg-elevated);
    font-size: var(--text-sm);
    font-weight: 600;
  }

  .dock-scope li > span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .dock-scope li > button {
    display: grid;
    width: 1.5rem;
    height: 1.5rem;
    padding: 0;
    place-items: center;
    border: 0;
    border-radius: var(--radius-full);
    background: transparent;
    color: var(--color-text-muted);
    cursor: pointer;
    transition: color var(--duration-fast) var(--ease-default), background var(--duration-fast) var(--ease-default), transform var(--duration-fast) var(--ease-default);
  }
  .dock-scope li.stale {
    border-style: dashed;
    color: var(--color-warning-text);
  }
  .dock-scope li.stale small {
    color: inherit;
    font-size: var(--text-xs);
    white-space: nowrap;
  }

  .dock-scope li > button:hover:not(:disabled) {
    color: var(--color-text-primary);
    background: var(--color-bg-surface);
  }

  .dock-scope li > button:active:not(:disabled) {
    transform: scale(0.96);
  }

  .dock-scope li > button:disabled {
    color: var(--color-text-muted);
    background: var(--color-bg-hover);
    cursor: not-allowed;
  }

  .dock-scope li > button :global(svg) {
    width: 0.8rem;
    height: 0.8rem;
  }

  .dock-scope p,
  .save-state {
    margin: 0;
    color: var(--color-text-muted);
    font-size: var(--text-sm);
    line-height: 1.4;
  }

  .save-state {
    margin-top: var(--space-1);
  }

  .save-state--error {
    display: flex;
    gap: var(--space-2);
    align-items: center;
    color: var(--color-error-text);
  }

  .save-state--error button {
    min-height: 1.5rem;
    padding: 0;
    border: 0;
    background: transparent;
    color: currentColor;
    font: inherit;
    font-weight: 700;
    text-decoration: underline;
    text-underline-offset: 0.2em;
    cursor: pointer;
  }

  .dock-commit {
    display: grid;
    gap: var(--space-1);
    justify-items: end;
    min-width: max-content;
  }

  .dock-cost {
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-11);
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    font-variant-numeric: tabular-nums;
    font-feature-settings: "zero" 0;
  }

  .dock-reason {
    max-width: 24rem;
    color: var(--color-text-muted);
    font-size: var(--text-xs);
    line-height: 1.3;
    text-align: right;
  }

  .review-action {
    display: inline-flex;
    min-width: 10rem;
    min-height: 2.5rem;
    align-items: center;
    justify-content: center;
    padding: 0 var(--space-4);
    border: 0;
    border-radius: var(--radius-md);
    background: var(--color-accent-hover);
    color: var(--color-text-on-accent);
    font: inherit;
    font-size: var(--text-13);
    font-weight: 700;
    cursor: pointer;
    transition: background var(--duration-fast) var(--ease-default), color var(--duration-fast) var(--ease-default), transform var(--duration-fast) var(--ease-default);
  }

  .review-action:hover:not(:disabled) {
    background: var(--color-accent-dark);
  }

  .review-action:active:not(:disabled) {
    transform: scale(0.98);
  }

  .review-action:disabled {
    background: var(--color-bg-hover);
    color: var(--color-text-muted);
    cursor: not-allowed;
  }

  button:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  @media (min-width: 80rem) {
    .decision-dock {
      left: calc(50% + 9.375rem);
      width: min(calc(100vw - 21rem), 75rem);
    }
  }

  @media (max-width: 64rem) {
    .decision-dock {
      grid-template-columns: auto auto minmax(0, 1fr) auto;
      gap: var(--space-2) var(--space-4);
    }

    .dock-count {
      grid-column: 1;
      grid-row: 1;
    }

    .dock-rule {
      grid-column: 2;
      grid-row: 1;
    }

    .dock-scope {
      grid-column: 3;
      grid-row: 1;
    }

    .dock-commit {
      display: flex;
      grid-column: 3;
      grid-row: 2;
      align-items: baseline;
      justify-content: flex-end;
      min-width: 0;
    }

    .review-action {
      grid-column: 4;
      grid-row: 1 / 3;
      align-self: center;
    }
  }

  @media (max-width: 40rem) {
    .decision-dock {
      bottom: 0;
      grid-template-columns: auto minmax(0, 1fr);
      gap: var(--space-2) var(--space-3);
      width: 100%;
      padding: var(--space-3) var(--space-4) calc(var(--space-3) + env(safe-area-inset-bottom));
      border-right: 0;
      border-bottom: 0;
      border-left: 0;
      border-radius: var(--radius-lg) var(--radius-lg) var(--radius-none) var(--radius-none);
    }

    .dock-count {
      grid-column: 1;
      grid-row: 1;
    }

    .dock-commit {
      display: grid;
      grid-column: 2;
      grid-row: 1;
      gap: var(--space-1);
    }

    .dock-reason {
      max-width: none;
    }

    .dock-scope {
      grid-column: 1 / -1;
      grid-row: 2;
    }

    .dock-rule,
    .dock-scope ul,
    .dock-scope > p,
    .save-state:not(.save-state--error) {
      display: none;
    }

    .review-action {
      grid-column: 1 / -1;
      grid-row: 3;
      width: 100%;
      min-height: 2.75rem;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .dock-scope li > button,
    .review-action {
      transition: none;
    }

    .dock-scope li > button:active,
    .review-action:active {
      transform: none;
    }
  }
</style>
