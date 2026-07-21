<script lang="ts">
  import { ArrowRight, Check, PencilLine, Plus, X } from "lucide-svelte";
  import type {
    SelectionJourney,
    SelectionJourneyTaskKey,
  } from "$lib/selection/decisionJourney";
  import { SECONDARY_TOOL_SLUGS } from "$lib/selection/labels";

  interface Props {
    journey: SelectionJourney;
    deepResearchCost?: number | null;
    busy?: boolean;
    saveState?: "idle" | "saving" | "saved" | "error";
    saveError?: string;
    saveConflict?: boolean;
    researchLeadTitle?: string;
    onRunRecommendation: () => void;
    onAddResearchLead?: () => void;
    onRemoveShortlistItem?: (ideaId: string, ideaRevision: number) => void;
    onOpenCandidates: () => void;
    onRetrySave: () => void;
    onReloadSave: () => void;
    onEditConstraints: () => void;
    onOpenCompare: () => void;
    onOpenRisks: () => void;
    onOpenTests: () => void;
    onOpenAlternatives: () => void;
    onStartDeepResearch: () => void;
  }

  let {
    journey,
    deepResearchCost = null,
    busy = false,
    saveState = "idle",
    saveError = "",
    saveConflict = false,
    researchLeadTitle = "",
    onRunRecommendation,
    onAddResearchLead,
    onRemoveShortlistItem,
    onOpenCandidates,
    onRetrySave,
    onReloadSave,
    onEditConstraints,
    onOpenCompare,
    onOpenRisks,
    onOpenTests,
    onOpenAlternatives,
    onStartDeepResearch,
  }: Props = $props();

  const shortlistCount = $derived(journey.shortlist.items.length);
  const shortlistFull = $derived(shortlistCount >= journey.shortlist.maxItems);

  // Foreground the decision-critical tools (constraints setup + Compare + Check
  // the evidence). Plan-a-test and Explore-variants are optional/divergent work,
  // demoted to a quiet "not ready to decide?" row so they stay discoverable
  // without reading as prerequisites.
  const primaryTasks = $derived(
    journey.tasks.filter((task) => !SECONDARY_TOOL_SLUGS.includes(task.key)),
  );
  const secondaryTasks = $derived(
    journey.tasks.filter((task) => SECONDARY_TOOL_SLUGS.includes(task.key)),
  );
  const recommendationOwnsResearchLead = $derived(
    journey.recommendation.target === "shortlist" && Boolean(researchLeadTitle),
  );
  const costLabel = $derived(
    deepResearchCost == null
      ? "Cost shown before you start"
      : `${deepResearchCost} credit${deepResearchCost === 1 ? "" : "s"}`,
  );

  function runTask(key: SelectionJourneyTaskKey) {
    if (busy) return;
    switch (key) {
      case "constraints":
        return onEditConstraints();
      case "compare":
        return onOpenCompare();
      case "risks":
        return onOpenRisks();
      case "tests":
        return onOpenTests();
      case "alternatives":
        return onOpenAlternatives();
    }
  }

  function taskDisabled(key: SelectionJourneyTaskKey): boolean {
    const status = journey.tasks.find((task) => task.key === key)?.status;
    return busy || status === "not_ready";
  }
</script>

<aside class="rail" aria-labelledby="decision-rail-title">
  <div class="selection-summary">
    <header class="rail-head">
      <div>
        <p class="eyebrow">Selection</p>
        <h2 id="decision-rail-title">Your decision</h2>
      </div>
      <p class="shortlist-count" aria-label={`${shortlistCount} of ${journey.shortlist.maxItems} shortlisted`}>
        <strong>{shortlistCount}</strong> / {journey.shortlist.maxItems}
      </p>
    </header>

    <section class="shortlist" aria-labelledby="shortlist-title">
      <div class="section-head">
        <h3 id="shortlist-title">Shortlist</h3>
        <button type="button" class="quiet-action" onclick={onOpenCandidates} disabled={busy}>Edit</button>
      </div>
      {#if journey.shortlist.items.length > 0}
        <ul>
          {#each journey.shortlist.items as idea (`${idea.ideaId}:${idea.ideaRevision}`)}
            <li data-idea-id={idea.ideaId} data-idea-revision={idea.ideaRevision}>
              <span class="pick-marker" aria-hidden="true"><Check /></span>
              <span class="pick-copy">
                <span class="pick-title">{idea.title}</span>
                <span class="pick-revision">Revision {idea.ideaRevision}</span>
              </span>
              <button
                type="button"
                class="remove-pick"
                aria-label={`Remove ${idea.title} from shortlist`}
                title="Remove from shortlist"
                onclick={() => onRemoveShortlistItem?.(idea.ideaId, idea.ideaRevision)}
                disabled={busy || !onRemoveShortlistItem}
              >
                <X aria-hidden="true" />
              </button>
            </li>
          {/each}
        </ul>
      {:else}
        <p class="empty-copy">Choose up to three ideas to take into Deep Research.</p>
      {/if}
      {#if saveState === "saving" || saveState === "error"}
        <div
          class:error={saveState === "error"}
          class="save-status"
          aria-live="polite"
          role={saveState === "error" ? "alert" : "status"}
        >
          {#if saveState === "saving"}
            <span>Saving shortlist…</span>
          {:else}
            <strong>Shortlist not saved</strong>
            {#if saveError}<span>{saveError}</span>{/if}
            <button type="button" onclick={saveConflict ? onReloadSave : onRetrySave}>
              {saveConflict ? "Reload" : "Retry"}
            </button>
          {/if}
        </div>
      {/if}
      {#if saveState === "saved"}<span class="sr-only" role="status">Shortlist saved</span>{/if}
    </section>
  </div>

  <section class="recommendation" aria-labelledby="recommendation-title">
    <p class="eyebrow">Recommended next</p>
    <h3 id="recommendation-title">{journey.recommendation.title}</h3>
    <p>{journey.recommendation.description}</p>
    {#if recommendationOwnsResearchLead}
      <div class="recommendation-candidate">
        <button
          type="button"
          class="recommendation-candidate-link"
          aria-label={journey.recommendation.actionLabel}
          onclick={onRunRecommendation}
          disabled={busy}
        >
          <span>{researchLeadTitle}</span>
          <span class="recommendation-review-label">
            Review details
            <ArrowRight aria-hidden="true" />
          </span>
        </button>
        <button
          type="button"
          class="recommendation-add"
          aria-label={shortlistFull
            ? `Shortlist is full; remove an idea before adding ${researchLeadTitle}`
            : `Add ${researchLeadTitle} to shortlist`}
          onclick={onAddResearchLead}
          disabled={busy || shortlistFull || !onAddResearchLead}
        >
          <Plus aria-hidden="true" />
          {shortlistFull ? "Remove a pick to add" : "Add to shortlist"}
        </button>
      </div>
    {:else}
      <button
        type="button"
        class="recommendation-action"
        class:editorial-action={journey.recommendation.target !== "deep_research"}
        onclick={onRunRecommendation}
        disabled={busy || (journey.recommendation.target === "deep_research" && !journey.deepResearch.eligible)}
      >
        {journey.recommendation.actionLabel}
        {#if journey.recommendation.target !== "deep_research"}<ArrowRight aria-hidden="true" />{/if}
      </button>
    {/if}
  </section>

  <div class="workflow-summary">
    <nav class="steps" aria-label="Decision tools">
      <h3>Decision tools</h3>
      <ul>
        {#each primaryTasks as task (task.key)}
          {@const locked = task.status === "not_ready"}
          <li>
            <button
              type="button"
              class:is-locked={locked}
              class:is-optional={task.status === "optional"}
              onclick={() => runTask(task.key)}
              disabled={taskDisabled(task.key)}
              aria-describedby={`decision-task-${task.key}-description`}
            >
              <span class="task-copy">
                <span class="task-title">
                  {task.title}
                  <!-- The icon says where the click goes: a form opens here,
                       everything else opens the workspace. -->
                  {#if task.key === "constraints"}
                    <PencilLine aria-hidden="true" />
                  {:else}
                    <ArrowRight aria-hidden="true" />
                  {/if}
                </span>
                <span class="task-description sr-only" id={`decision-task-${task.key}-description`}>{task.description}</span>
                <!-- A lock is not a status: it states what to do, on its own
                     line, instead of competing with progress in the badge. -->
                {#if locked}
                  <span class="task-lock">{task.statusLabel}</span>
                {/if}
              </span>
              {#if !locked}
                <span class="task-status" data-status={task.status}>{task.statusLabel}</span>
              {/if}
            </button>
          </li>
        {/each}
      </ul>

      {#if secondaryTasks.length > 0}
        <div class="secondary" aria-label="Optional next steps">
          <span class="secondary-label">Not ready to decide?</span>
          <div class="secondary-actions">
            {#each secondaryTasks as task (task.key)}
              <button type="button" class="secondary-action" onclick={() => runTask(task.key)} disabled={busy}>
                {task.title}
                <ArrowRight aria-hidden="true" />
              </button>
            {/each}
          </div>
        </div>
      {/if}
    </nav>

    <footer class="commit">
      <div>
        <h3>{journey.deepResearch.eligible ? "Ready when you are" : "Choose an idea to continue"}</h3>
        <p>{costLabel}</p>
      </div>
      <button
        type="button"
        class="commit-action"
        onclick={onStartDeepResearch}
        disabled={busy || !journey.deepResearch.eligible}
      >
        Start Deep Research
      </button>
    </footer>
  </div>
</aside>

<style>
  .rail {
    --rail-ink: var(--color-text-primary);
    --rail-muted: var(--color-text-secondary);
    --rail-accent: var(--color-accent-hover);
    --rail-accent-soft: color-mix(in srgb, var(--color-accent) 7%, var(--color-bg-elevated));
    --rail-surface: var(--color-bg-elevated);
    --rail-subtle: var(--color-bg-surface);
    color: var(--rail-ink);
    background: var(--rail-surface);
    border: 1px solid var(--color-border-emphasis);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
    overflow: hidden;
  }

  .selection-summary,
  .workflow-summary {
    display: contents;
  }

  .rail-head,
  .section-head,
  .commit {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }

  .rail-head {
    padding: 1.2rem 1.125rem 0.9rem;
  }

  .eyebrow {
    margin: 0 0 0.35rem;
    color: var(--rail-muted);
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }

  h2,
  h3,
  p {
    margin-top: 0;
  }

  h2 {
    margin-bottom: 0;
    font-size: 1.35rem;
    letter-spacing: -0.035em;
  }

  h3 {
    margin-bottom: 0;
    font-size: 0.94rem;
    letter-spacing: -0.015em;
  }

  .shortlist-count {
    margin: 0;
    color: var(--rail-muted);
    font-variant-numeric: tabular-nums;
  }

  .shortlist-count strong {
    color: var(--rail-ink);
    font-size: 1.25rem;
  }

  .shortlist,
  .recommendation,
  .steps,
  .commit {
    padding: 1rem 1.125rem;
    border-top: 1px solid var(--color-border);
  }

  .quiet-action {
    appearance: none;
    border: 0;
    min-height: 1.75rem;
    padding: 0.35rem 0.4rem;
    margin-right: -0.4rem;
    border-radius: var(--radius-sm);
    color: var(--rail-accent);
    background: transparent;
    font: inherit;
    font-size: var(--text-13);
    font-weight: 700;
    cursor: pointer;
    transition: text-decoration-color var(--duration-fast) var(--ease-default);
  }
  .quiet-action:hover:not(:disabled) {
    text-decoration: underline;
    text-underline-offset: 0.2rem;
  }

  ul {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .shortlist ul {
    display: grid;
    gap: 0.55rem;
    margin-top: 0.8rem;
  }

  .shortlist li {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    gap: 0.7rem;
    min-width: 0;
    padding: 0.72rem;
    border-radius: 0.9rem;
    background: var(--rail-subtle);
  }

  .remove-pick {
    display: grid;
    width: 1.8rem;
    height: 1.8rem;
    place-items: center;
    border: 0;
    border-radius: 999px;
    color: var(--rail-muted);
    background: transparent;
    cursor: pointer;
    transition:
      color var(--duration-fast) var(--ease-default),
      background-color var(--duration-fast) var(--ease-default);
  }

  .remove-pick:hover:not(:disabled) {
    color: var(--color-error-text);
    background: var(--color-error-subtle);
  }

  .remove-pick :global(svg) {
    width: 0.9rem;
    height: 0.9rem;
  }

  .remove-pick:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .pick-marker {
    display: grid;
    flex: 0 0 1.55rem;
    width: 1.55rem;
    height: 1.55rem;
    place-items: center;
    border-radius: 999px;
    color: var(--rail-accent);
    background: var(--color-bg-elevated);
    box-shadow: inset 0 0 0 1px var(--color-border-accent);
    font-size: 0.75rem;
    font-weight: 700;
  }

  .pick-marker :global(svg) {
    width: 0.9rem;
    height: 0.9rem;
    stroke-width: 2.4;
  }

  .pick-copy,
  .task-copy {
    display: grid;
    min-width: 0;
  }

  .pick-title {
    overflow: hidden;
    font-size: 0.84rem;
    font-weight: 700;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .pick-revision,
  .task-description,
  .empty-copy,
  .recommendation p,
  .commit p {
    color: var(--rail-muted);
    font-size: 0.78rem;
    line-height: 1.5;
  }

  .pick-revision {
    margin-top: 0.08rem;
  }

  .empty-copy {
    margin: 0.75rem 0 0;
  }

  .save-status {
    display: flex;
    gap: 0.45rem;
    align-items: center;
    margin-top: 0.8rem;
    color: var(--rail-muted);
    font-size: 0.74rem;
    line-height: 1.4;
  }

  .save-status.error {
    align-items: flex-start;
    flex-direction: column;
    color: var(--color-error-text);
  }

  .save-status button {
    border: 0;
    min-height: 1.75rem;
    padding: 0.25rem 0;
    color: currentColor;
    background: transparent;
    font: inherit;
    font-weight: 700;
    text-decoration: underline;
    text-underline-offset: 0.18em;
    text-decoration-thickness: 1px;
    cursor: pointer;
    transition: text-decoration-thickness var(--duration-fast) var(--ease-default);
  }
  .save-status button:hover {
    text-decoration-thickness: 2px;
  }

  .recommendation {
    background: var(--rail-accent-soft);
  }

  .recommendation h3 {
    font-size: 1.05rem;
  }

  .recommendation p {
    margin: 0.55rem 0 1rem;
    color: var(--color-text-secondary);
  }

  .recommendation-candidate {
    display: grid;
    gap: 0.75rem;
    padding-top: 0.85rem;
    border-top: 1px solid color-mix(in srgb, var(--rail-accent) 18%, var(--color-border));
  }

  .recommendation-candidate-link {
    display: grid;
    width: 100%;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 0.8rem;
    align-items: center;
    border: 0;
    padding: 0;
    color: var(--rail-ink);
    text-align: left;
    background: transparent;
    font: inherit;
    cursor: pointer;
  }

  .recommendation-candidate-link > span:first-child {
    overflow: hidden;
    font-size: 0.9rem;
    font-weight: 700;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .recommendation-review-label {
    display: inline-flex;
    gap: 0.35rem;
    align-items: center;
    color: var(--rail-accent);
    font-size: 0.72rem;
    font-weight: 700;
    white-space: nowrap;
  }

  .recommendation-review-label :global(svg),
  .recommendation-add :global(svg) {
    width: 0.85rem;
    height: 0.85rem;
    stroke-width: 2.3;
  }

  .recommendation-add {
    display: inline-flex;
    width: fit-content;
    min-height: 2.35rem;
    align-items: center;
    justify-content: center;
    gap: 0.45rem;
    border: 0;
    border-radius: var(--radius-sm);
    padding: 0.55rem 0.8rem;
    color: var(--color-text-on-accent);
    background: var(--rail-accent);
    font: inherit;
    font-size: 0.78rem;
    font-weight: 700;
    cursor: pointer;
    transition: background-color var(--duration-fast) var(--ease-default);
  }

  .recommendation-candidate-link:hover:not(:disabled) .recommendation-review-label {
    color: var(--color-accent-dark);
  }

  .recommendation-add:hover:not(:disabled) {
    background: var(--color-accent-dark);
  }

  .recommendation-action,
  .commit-action {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.55rem;
    min-height: 2.75rem;
    border: 0;
    border-radius: var(--radius-md);
    padding: 0.7rem 1.05rem;
    color: var(--color-text-on-accent);
    background: var(--rail-accent);
    font: inherit;
    font-size: 0.85rem;
    font-weight: 700;
    cursor: pointer;
    transition: background-color var(--duration-fast) var(--ease-default);
  }

  .recommendation-action :global(svg) {
    width: 0.95rem;
    height: 0.95rem;
    transition: transform 220ms cubic-bezier(0.32, 0.72, 0, 1);
  }

  .recommendation-action.editorial-action {
    border: 1px solid color-mix(in srgb, var(--rail-accent) 32%, transparent);
    color: var(--rail-accent);
    background: var(--rail-surface);
  }

  .recommendation-action.editorial-action:hover:not(:disabled) {
    color: var(--color-accent-dark);
    background: var(--rail-surface);
  }

  .recommendation-action.editorial-action:hover:not(:disabled) :global(svg) {
    transform: translateX(0.18rem);
  }

  .recommendation-candidate-link:focus-visible,
  .recommendation-add:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .recommendation-action:hover:not(:disabled),
  .commit-action:hover:not(:disabled) {
    background: var(--color-accent-dark);
  }

  .steps h3 {
    margin-bottom: 0.7rem;
  }

  .steps ul {
    display: grid;
  }

  .steps li + li {
    border-top: 1px solid var(--color-border);
  }

  .steps button {
    display: grid;
    width: 100%;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 0.8rem;
    align-items: center;
    border: 0;
    padding: 0.68rem 0.5rem;
    margin-inline: -0.5rem;
    width: calc(100% + 1rem);
    border-radius: var(--radius-md);
    text-align: left;
    background: transparent;
    font: inherit;
    cursor: pointer;
    transition: background var(--duration-fast) var(--ease-default);
  }

  /* The primary decision-tool rows are the rail's main navigation — give them
     pointer feedback like any nav item. */
  .steps button:hover:not(:disabled) {
    background: var(--rail-subtle);
  }
  .steps button:active:not(:disabled) {
    background: var(--rail-accent-soft);
  }

  .task-title {
    display: inline-flex;
    gap: 0.4rem;
    align-items: center;
    font-size: var(--text-13);
    font-weight: 700;
  }

  .task-title :global(svg) {
    width: 0.75rem;
    height: 0.75rem;
    color: var(--rail-muted);
    stroke-width: 2;
  }

  .task-description {
    margin-top: 0.18rem;
  }

  .task-status {
    border-radius: var(--radius-md);
    padding: 0.25rem 0.5rem;
    color: var(--rail-muted);
    background: var(--rail-subtle);
    font-size: var(--text-11);
    font-weight: 700;
    white-space: nowrap;
  }

  .task-status[data-status="recommended"],
  .task-status[data-status="needs_refresh"] {
    color: var(--color-accent-dark);
    background: var(--rail-accent-soft);
  }

  .task-status[data-status="complete"] {
    color: var(--color-success-dark);
    background: color-mix(in srgb, var(--color-success-dark) 8%, var(--color-bg-elevated));
  }

  /* Optional work should read as available, not as a labelled exception. */
  .task-status[data-status="optional"] {
    background: transparent;
    padding-inline: 0;
    font-weight: 600;
  }

  .task-lock {
    display: block;
    margin-top: 0.2rem;
    color: var(--rail-muted);
    font-size: var(--text-sm);
    font-weight: 600;
  }

  /* Demoted tools: discoverable, clearly optional, not co-equal with the two
     primary decisions above. */
  .secondary {
    margin-top: 0.85rem;
    padding-top: 0.85rem;
    border-top: 1px solid var(--color-border);
  }
  .secondary-label {
    display: block;
    margin-bottom: 0.5rem;
    color: var(--rail-muted);
    font-size: var(--text-sm);
    font-weight: 600;
  }
  .secondary-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
  }
  .secondary-action {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.35rem 0.6rem;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: transparent;
    color: var(--rail-muted);
    font: inherit;
    font-size: var(--text-sm);
    font-weight: 600;
    cursor: pointer;
    transition: border-color 160ms var(--ease-default), color 160ms var(--ease-default), transform var(--duration-fast) var(--ease-default);
  }
  .secondary-action:hover:not(:disabled) {
    border-color: var(--color-border-emphasis);
    color: var(--rail-ink, var(--color-text-primary));
  }
  .secondary-action:active:not(:disabled) { transform: scale(0.98); }
  .secondary-action:disabled { cursor: not-allowed; opacity: var(--opacity-disabled); }
  .secondary-action :global(svg) { width: 0.7rem; height: 0.7rem; }

  /* A locked step stays legible: the row dims, the instruction does not. */
  .steps button.is-locked {
    cursor: not-allowed;
  }

  .steps button.is-locked .task-title {
    opacity: 0.55;
  }

  button:disabled {
    cursor: not-allowed;
  }

  button:disabled:not(.is-locked) {
    opacity: 0.5;
  }

  .commit {
    align-items: stretch;
    flex-direction: column;
  }

  .commit h3 {
    margin-bottom: 0.18rem;
  }

  .commit p {
    margin-bottom: 0;
  }

  .commit-action {
    width: 100%;
    background: var(--color-text-primary);
  }

  .commit-action:hover:not(:disabled) {
    background: var(--color-text-secondary);
  }

  .commit-action:active:not(:disabled) {
    transform: scale(0.99);
  }

  @container selection-workbench (min-width: 48.01rem) and (max-width: 72rem) {
    .rail {
      display: grid;
      grid-template-columns: minmax(16rem, 0.95fr) minmax(17rem, 1fr) minmax(21rem, 1.2fr);
      align-items: start;
    }

    .selection-summary,
    .workflow-summary {
      display: flex;
      min-width: 0;
      flex-direction: column;
    }

    .rail-head,
    .shortlist,
    .recommendation,
    .steps,
    .commit {
      padding: 1.1rem 1.2rem;
      border-top: 0;
    }

    .shortlist,
    .commit {
      border-top: 1px solid var(--color-border);
    }

    .recommendation,
    .workflow-summary {
      border-left: 1px solid var(--color-border);
    }

    .recommendation {
      display: flex;
      flex-direction: column;
      justify-content: center;
    }

    .shortlist {
      flex: 1;
    }

    .recommendation-action {
      align-self: flex-start;
    }

    .steps button {
      padding-block: 0.46rem;
    }

    .commit {
      margin-top: auto;
      justify-content: center;
    }
  }

  @media (max-width: 48rem) {
    .rail {
      border-radius: 1.15rem;
    }

    .rail-head,
    .shortlist,
    .recommendation,
    .steps,
    .commit {
      padding-inline: 1rem;
    }

    .commit {
      align-items: stretch;
      flex-direction: column;
    }

    .commit-action,
    .recommendation-action {
      width: 100%;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .recommendation-action,
    .recommendation-action :global(svg),
    .commit-action,
    .steps button {
      transition: none;
    }
    .steps button:active,
    .secondary-action:active,
    .commit-action:active {
      transform: none;
    }
  }
</style>
