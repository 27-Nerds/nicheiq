<script lang="ts">
  import type { PageData } from "./$types";
  import { solutionDisplayTitle } from "$lib/utils/solution-utils";
  import { getWorkspaceTools } from "$lib/selection/workspaceTools";
  let { data }: { data: PageData } = $props();

  const tools = getWorkspaceTools();

  const lenses = [
    { key: "demand", label: "Customer demand" },
    { key: "distribution", label: "Reachability" },
    { key: "competition", label: "Competition" },
    { key: "dependencies", label: "Dependencies" },
  ] as const;

  type LensKey = (typeof lenses)[number]["key"];

  function lensHref(lens: LensKey): string {
    const params = new URLSearchParams(data.workspace.canonicalQuery.slice(1));
    params.set("lens", lens);
    return `?${params.toString()}`;
  }

  /** Opens the evidence review in place, on the lens the page is already
   *  showing, so the page-level lens and the review agree. */
  function openReview(ideaId: string | undefined, ideaRevision: number | undefined, lens?: LensKey): void {
    if (!ideaId) return;
    tools.openChallenge({ ideaId, ideaRevision: ideaRevision ?? 1, lens: lens ?? data.workspace.lens });
  }

  function challengeFor(ideaId: string | undefined, ideaRevision: number | undefined, lens: LensKey) {
    return data.decisionState?.challenges.find((challenge) => (
      challenge.idea.ideaId === ideaId
      && challenge.idea.ideaRevision === (ideaRevision ?? 1)
      && challenge.lens === lens
    )) ?? null;
  }

  function assumptionsFor(ideaId: string | undefined, ideaRevision: number | undefined, lens: LensKey) {
    return data.decisionState?.assumptions.filter((assumption) => (
      assumption.idea.ideaId === ideaId
      && assumption.idea.ideaRevision === (ideaRevision ?? 1)
      && assumption.lens === lens
    )) ?? [];
  }

  // Each candidate's status across ALL four lenses — the evidence map. A lens is
  // "open" when its review surfaced unresolved questions, "clear" when the
  // evidence held up, and "unchecked" until reviewed. This is what makes the
  // card informative before a single review is run.
  type LensState = "open" | "clear" | "unchecked";
  function lensStatus(ideaId: string | undefined, ideaRevision: number | undefined, lens: LensKey): LensState {
    const challenge = challengeFor(ideaId, ideaRevision, lens);
    if (!challenge) return "unchecked";
    return challenge.gapQuestionIds.length > 0 ? "open" : "clear";
  }

  const activeLens = $derived(data.workspace.lens as LensKey);
  const activeLensLabel = $derived(lenses.find((l) => l.key === activeLens)?.label ?? activeLens);

  const STATE_COPY: Record<LensState, string> = {
    open: "Open questions",
    clear: "Holds up",
    unchecked: "Not checked",
  };
</script>

<section class="selection-page">
  <header class="selection-page__header">
    <div>
      <h2>What could change your mind before you pay to research?</h2>
      <p class="selection-page__lead">Two independent passes stress-test the captured evidence for each finalist. Nothing here moves your shortlist or scores.</p>
    </div>
  </header>

  <nav class="lens-bar" aria-label="Evidence area">
    {#each lenses as lens}
      <a
        class:active={activeLens === lens.key}
        href={lensHref(lens.key)}
        aria-current={activeLens === lens.key ? "page" : undefined}
      >{lens.label}</a>
    {/each}
  </nav>

  <div class:single-candidate={data.workspace.ideas.length === 1} class="risk-list">
    {#each data.workspace.ideas as idea, i}
      {@const state = lensStatus(idea.idea_id, idea.idea_revision, activeLens)}
      {@const challenge = challengeFor(idea.idea_id, idea.idea_revision, activeLens)}
      {@const assumptions = assumptionsFor(idea.idea_id, idea.idea_revision, activeLens)}
      <article class="risk-card">
        <div class="risk-head">
          <span class="candidate-index" aria-hidden="true">{i + 1}</span>
          <div class="candidate-id">
            <h3>{solutionDisplayTitle(idea)}</h3>
            {#if (idea.idea_revision ?? 1) > 1}<span class="rev">rev {idea.idea_revision}</span>{/if}
          </div>
          <span class="lens-state" data-state={state}>{STATE_COPY[state]}</span>
        </div>

        <div class="lens-map" role="group" aria-label="Evidence checked across areas">
          {#each lenses as lens}
            {@const s = lensStatus(idea.idea_id, idea.idea_revision, lens.key)}
            <a
              class="lens-cell"
              class:current={lens.key === activeLens}
              data-state={s}
              href={lensHref(lens.key)}
              aria-label={`${lens.label}: ${STATE_COPY[s]}`}
              aria-current={lens.key === activeLens ? "true" : undefined}
            >
              <span class="lens-dot" data-state={s} aria-hidden="true">
                {#if s === "clear"}<svg viewBox="0 0 10 10" aria-hidden="true"><path d="M2 5.2 4.2 7.4 8 3" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
                {:else if s === "open"}<svg viewBox="0 0 10 10" aria-hidden="true"><path d="M5 2.4v3.1M5 7.3v.3" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>{/if}
              </span>
              <span class="lens-name">{lens.label}</span>
            </a>
          {/each}
        </div>

        <p class="lens-detail">
          {#if challenge}
            {challenge.gapQuestionIds.length > 0
              ? `${challenge.gapQuestionIds.length} open ${challenge.gapQuestionIds.length === 1 ? "question" : "questions"} in ${activeLensLabel.toLowerCase()} could change this choice.`
              : `The captured ${activeLensLabel.toLowerCase()} evidence holds up.`}
          {:else}
            {idea.critic_concern ?? `No independent check has run on ${activeLensLabel.toLowerCase()} for this candidate yet.`}
          {/if}
        </p>

        <div class="risk-actions">
          <button type="button" class="review-action" onclick={() => openReview(idea.idea_id, idea.idea_revision)}>
            {challenge ? "Reopen review" : "Run evidence review"}
            <span class="link-arrow" aria-hidden="true">→</span>
          </button>
          {#if assumptions.length > 0}
            <button type="button" class="tracked-count" onclick={() => tools.openAssumptions({
              ideaId: idea.idea_id ?? "",
              ideaRevision: idea.idea_revision ?? 1,
              lens: activeLens,
            })}>
              {assumptions.length} tracked {assumptions.length === 1 ? "assumption" : "assumptions"}
            </button>
          {/if}
        </div>
      </article>
    {:else}
      <div class="selection-page__panel selection-page__empty"><div><h3>No candidate is in scope</h3><p>Add a candidate to your shortlist above, then check the evidence behind it.</p></div></div>
    {/each}
  </div>
</section>

<style>
  .lens-bar { display: flex; gap: 0.3rem; overflow-x: auto; margin-bottom: 1rem; padding-bottom: 0.25rem; }
  .lens-bar a { flex: 0 0 auto; min-height: 1.75rem; display: inline-flex; align-items: center; padding: 0.375rem 0.75rem; border-radius: var(--radius-md); color: var(--color-text-secondary); font-size: var(--text-13); font-weight: 700; text-decoration: none; transition: background var(--duration-fast) var(--ease-default), color var(--duration-fast) var(--ease-default); }
  .lens-bar a:hover { color: var(--color-text-primary); }
  .lens-bar a.active { background: var(--color-accent-subtle); color: var(--color-accent-dark); box-shadow: inset 0 0 0 1px var(--color-border-accent); }

  .risk-list { display: grid; gap: 0.65rem; }
  .risk-list.single-candidate { max-width: 60rem; }

  .risk-card {
    display: grid;
    gap: 0.75rem;
    padding: 1rem 1.1rem;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-bg-elevated);
    box-shadow: var(--shadow-sm);
  }

  .risk-head { display: flex; align-items: center; gap: 0.6rem; }
  .candidate-index { display: grid; flex: 0 0 auto; width: 1.35rem; height: 1.35rem; place-items: center; border-radius: 50%; background: var(--color-bg-surface); color: var(--color-text-secondary); font: 700 var(--text-11)/1 var(--font-mono); font-variant-numeric: tabular-nums; }
  .candidate-id { display: flex; flex: 1; min-width: 0; align-items: baseline; gap: 0.5rem; }
  .candidate-id h3 { overflow: hidden; margin: 0; font-size: var(--text-base); font-weight: 700; letter-spacing: -0.005em; text-overflow: ellipsis; white-space: nowrap; }
  .rev { flex: 0 0 auto; color: var(--color-text-muted); font: 600 var(--text-xs)/1 var(--font-mono); }

  /* Status pill — severity semantics, not brand orange (open = attention). */
  .lens-state { flex: 0 0 auto; padding: 0.2rem 0.5rem; border-radius: 999px; font: 700 var(--text-xs)/1.3 var(--font-mono); letter-spacing: 0.04em; text-transform: uppercase; white-space: nowrap; }
  .lens-state[data-state="open"] { color: var(--color-warning-dark); background: var(--color-warning-subtle); }
  .lens-state[data-state="clear"] { color: var(--color-success-dark); background: var(--color-success-subtle); }
  .lens-state[data-state="unchecked"] { color: var(--color-text-secondary); background: var(--color-bg-surface); }

  /* The evidence map: all four lenses at a glance. Signature element. State is
     encoded by GLYPH (check / bar-dot / hollow) as well as color, so it reads
     without color vision; colors use the AA-tuned -dark tokens for 3:1. */
  .lens-map { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.375rem; }
  .lens-cell { display: flex; align-items: center; gap: 0.375rem; min-width: 0; min-height: 1.75rem; padding: 0.375rem 0.5rem; border: 1px solid var(--color-border); border-radius: var(--radius-md); color: var(--color-text-secondary); text-decoration: none; transition: border-color var(--duration-fast) var(--ease-default), background var(--duration-fast) var(--ease-default); }
  .lens-cell:hover { border-color: var(--color-border-emphasis); }
  .lens-cell:active { background: var(--color-bg-surface); }
  .lens-cell.current { border-color: var(--color-border-accent); background: var(--color-accent-subtle); }
  .lens-name { overflow: hidden; font-size: var(--text-sm); font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
  .lens-dot { display: grid; flex: 0 0 auto; width: 0.75rem; height: 0.75rem; place-items: center; border-radius: 50%; color: var(--color-bg-elevated); background: var(--color-text-muted); }
  .lens-dot svg { width: 0.6rem; height: 0.6rem; }
  .lens-dot[data-state="open"] { background: var(--color-warning-dark); }
  .lens-dot[data-state="clear"] { background: var(--color-success-dark); }
  .lens-dot[data-state="unchecked"] { background: transparent; box-shadow: inset 0 0 0 1.5px var(--color-text-muted); }

  .lens-detail { max-width: 78ch; margin: 0; color: var(--color-text-secondary); font-size: var(--text-13); line-height: 1.5; }

  .risk-actions { display: flex; align-items: center; gap: 0.75rem; }
  .review-action { display: inline-flex; gap: 0.375rem; align-items: center; min-height: 1.75rem; padding: 0.375rem 0.75rem 0.375rem 0.875rem; border: 0; border-radius: var(--radius-md); background: var(--color-accent-hover); color: var(--color-text-on-accent); font: inherit; font-size: var(--text-sm); font-weight: 700; cursor: pointer; transition: background var(--duration-fast) var(--ease-default), transform var(--duration-fast) var(--ease-default); }
  .review-action:hover { background: var(--color-accent-dark); }
  .review-action:active { transform: scale(0.98); }
  .link-arrow { display: inline-grid; place-items: center; transition: transform 220ms cubic-bezier(0.32, 0.72, 0, 1); }
  .review-action:hover .link-arrow { transform: translateX(0.15rem); }
  .tracked-count { padding: 0.25rem 0; border: 0; background: transparent; color: var(--color-accent-dark); font: inherit; font-size: var(--text-sm); font-weight: 700; cursor: pointer; }
  .tracked-count:hover { text-decoration: underline; text-underline-offset: 0.2rem; }

  @media (max-width: 767px) {
    .risk-card { padding: 1rem; }
    .lens-map { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .risk-actions { flex-wrap: wrap; }
  }
  @media (prefers-reduced-motion: reduce) {
    .review-action, .review-action:active { transform: none; }
  }
  @media (prefers-reduced-motion: reduce) {
    .link-arrow, .lens-cell, .lens-bar a, .review-action { transition: none; }
  }
</style>
