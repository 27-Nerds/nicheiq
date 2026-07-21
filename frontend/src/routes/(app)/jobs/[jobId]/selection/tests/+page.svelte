<script lang="ts">
  import { page } from "$app/state";
  import type { PageData } from "./$types";
  import { solutionDisplayTitle } from "$lib/utils/solution-utils";
  import { getWorkspaceTools } from "$lib/selection/workspaceTools";
  let { data }: { data: PageData } = $props();

  const tools = getWorkspaceTools();

  function assumptionsFor(ideaId: string | undefined, ideaRevision: number | undefined) {
    return data.decisionState?.assumptions.filter((assumption) => (
      assumption.idea.ideaId === ideaId && assumption.idea.ideaRevision === (ideaRevision ?? 1)
    )) ?? [];
  }

  function experimentsFor(ideaId: string | undefined, ideaRevision: number | undefined) {
    return data.decisionState?.experiments.filter((experiment) => (
      experiment.idea.ideaId === ideaId && experiment.idea.ideaRevision === (ideaRevision ?? 1)
    )) ?? [];
  }

  function ideaRef(ideaId: string | undefined, ideaRevision: number | undefined): string {
    return `${ideaId ?? ""}:${ideaRevision ?? 1}`;
  }

  const focusedIdea = $derived.by(() => {
    const requested = page.url.searchParams.get("focus");
    const exact = requested
      ? data.workspace.ideas.find((idea) => ideaRef(idea.idea_id, idea.idea_revision) === requested)
      : undefined;
    if (exact) return exact;
    return data.workspace.ideas.find((idea) => assumptionsFor(idea.idea_id, idea.idea_revision).length > 0)
      ?? data.workspace.ideas[0];
  });

  function focusHref(ideaId: string | undefined, ideaRevision: number | undefined): string {
    const params = new URLSearchParams(data.workspace.canonicalQuery.slice(1));
    params.set("focus", ideaRef(ideaId, ideaRevision));
    return `?${params.toString()}`;
  }

  /** Both paths open in place. With a tracked assumption we go straight to the
   *  planner seeded from it; without one we open the assumption tab first,
   *  because a test that does not start from an assumption is a checklist. */
  function openPlanning(
    hasAssumption: boolean,
    ideaId: string | undefined,
    ideaRevision: number | undefined,
    assumptionId?: string,
  ): void {
    if (!ideaId) return;
    const revision = ideaRevision ?? 1;
    if (hasAssumption) {
      tools.openTestPlanner({ ideaId, ideaRevision: revision, assumptionId });
      return;
    }
    tools.openAssumptions({ ideaId, ideaRevision: revision, lens: data.workspace.lens });
  }
</script>

<section class="selection-page">
  <header class="selection-page__header">
    <div>
      <h2>Decide what evidence would change your mind</h2>
      <p class="selection-page__lead">A useful test begins with one exact candidate and one risky assumption, not a generic validation checklist.</p>
    </div>
  </header>

  {#if data.workspace.ideas.length > 1}
    <nav class="candidate-focus" aria-label="Candidate to test">
      <span>Candidate</span>
      {#each data.workspace.ideas as idea}
        <a
          class:active={focusedIdea?.idea_id === idea.idea_id && (focusedIdea?.idea_revision ?? 1) === (idea.idea_revision ?? 1)}
          href={focusHref(idea.idea_id, idea.idea_revision)}
        >{solutionDisplayTitle(idea)}</a>
      {/each}
    </nav>
  {/if}

  <div class="test-focus">
    {#if focusedIdea}
      {@const assumptions = assumptionsFor(focusedIdea.idea_id, focusedIdea.idea_revision)}
      {@const experiments = experimentsFor(focusedIdea.idea_id, focusedIdea.idea_revision)}
      {@const assumption = assumptions[0]}
      <article class="test-card selection-page__panel">
        <div class="test-copy">
          <span class="step">Candidate in focus</span>
          <h3>{solutionDisplayTitle(focusedIdea)}</h3>
          <p class="risk">{assumption?.statement ?? focusedIdea.critic_concern ?? focusedIdea.source_pain ?? "No decision-changing assumption has been recorded yet."}</p>
          <div class="test-status" aria-label="Test status">
            <span>{assumptions.length} tracked {assumptions.length === 1 ? "assumption" : "assumptions"}</span>
            <span>{experiments.length} test {experiments.length === 1 ? "brief" : "briefs"}</span>
            {#if experiments.some((experiment) => experiment.conclusionId)}<span>Outcome recorded</span>{/if}
          </div>
        </div>
        <div class="test-plan">
          <p class="plan-label">Before you collect results</p>
          <ol aria-label="Test planning steps">
            <li class:complete={assumptions.length > 0}><span>1</span>Choose one assumption</li>
            <li class:complete={experiments.length > 0}><span>2</span>Define an observable signal</li>
            <li class:complete={experiments.length > 0}><span>3</span>Set success and stop rules</li>
          </ol>
          <button
            type="button"
            class="selection-page__link"
            onclick={() => openPlanning(
              assumptions.length > 0,
              focusedIdea.idea_id,
              focusedIdea.idea_revision,
              assumption?.id,
            )}
          >
            {assumptions.length > 0 ? "Open test planner" : "Track the assumption first"}
            <span class="link-arrow" aria-hidden="true">→</span>
          </button>
        </div>
      </article>
    {:else}
      <div class="selection-page__panel selection-page__empty"><div><h3>No candidate is ready for a test</h3><p>Add a candidate to your shortlist above, then check its evidence to find what is worth testing.</p></div></div>
    {/if}
  </div>
</section>

<style>
  .candidate-focus { display: flex; align-items: center; gap: 0.5rem; overflow-x: auto; margin-bottom: 1rem; padding-bottom: 0.25rem; }
  .candidate-focus > span { flex: 0 0 auto; color: var(--color-text-muted); font-size: var(--text-13); font-weight: 700; }
  .candidate-focus a { flex: 0 1 21rem; min-height: 1.75rem; display: inline-flex; align-items: center; overflow: hidden; padding: 0.375rem 0.75rem; border: 1px solid transparent; border-radius: var(--radius-md); color: var(--color-text-secondary); background: var(--color-bg-surface); font-size: var(--text-13); font-weight: 700; text-decoration: none; text-overflow: ellipsis; white-space: nowrap; transition: background var(--duration-fast) var(--ease-default), color var(--duration-fast) var(--ease-default), border-color var(--duration-fast) var(--ease-default); }
  .candidate-focus a:hover:not(.active) { color: var(--color-text-primary); border-color: var(--color-border-emphasis); }
  .candidate-focus a.active { border-color: var(--color-border-accent); color: var(--color-accent-dark); background: var(--color-accent-subtle); }
  .test-focus { max-width: 60rem; }
  .test-card { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(15rem, 0.85fr); gap: 2rem; padding: 1.25rem; border: 1px solid var(--color-border); border-radius: var(--radius-lg); background: var(--color-bg-elevated); box-shadow: var(--shadow-sm); }
  .step { color: var(--color-accent-dark); font: 700 var(--text-11)/1.3 var(--font-mono); letter-spacing: 0.12em; text-transform: uppercase; }
  .test-card h3 { margin: 0.5rem 0 0; font-family: var(--font-display); font-size: var(--text-md); line-height: 1.35; }
  .risk { max-width: 42rem; margin: 0.5rem 0 1rem; color: var(--color-text-secondary); font-size: var(--text-13); line-height: 1.55; }
  .test-status { display: flex; flex-wrap: wrap; gap: 0.375rem; }
  .test-status span { padding: 0.25rem 0.5rem; border-radius: var(--radius-sm); color: var(--color-text-secondary); background: var(--color-bg-surface); font: 700 var(--text-xs)/1.2 var(--font-mono); text-transform: uppercase; }
  .test-plan { display: flex; min-width: 0; flex-direction: column; justify-content: center; padding-left: 1.5rem; border-left: 1px solid var(--color-border); }
  .plan-label { margin: 0 0 0.75rem; color: var(--color-text-muted); font-size: var(--text-sm); font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; }
  ol { display: grid; gap: 0.5rem; margin: 0; padding: 0; list-style: none; }
  li { display: flex; align-items: center; gap: 0.625rem; color: var(--color-text-secondary); font-size: var(--text-13); }
  li span { display: grid; width: 1.5rem; height: 1.5rem; place-items: center; border-radius: 50%; background: var(--color-bg-surface); color: var(--color-text-muted); font: 700 var(--text-11)/1 var(--font-mono); }
  li.complete span { color: var(--color-success-dark); background: var(--color-success-subtle); }
  .test-card .selection-page__link { gap: 0.5rem; align-self: flex-start; margin-top: 1.25rem; }
  .link-arrow { display: grid; width: 1.6rem; height: 1.6rem; place-items: center; border-radius: 50%; background: var(--color-accent-subtle); transition: transform 220ms cubic-bezier(0.32, 0.72, 0, 1); }
  .test-card .selection-page__link:hover .link-arrow { transform: translateX(0.2rem); }
  @media (max-width: 767px) { .test-card { grid-template-columns: 1fr; gap: 1.25rem; padding: 1rem; } .test-plan { padding: 1.25rem 0 0; border-top: 1px solid var(--color-border); border-left: 0; } }
  @media (prefers-reduced-motion: reduce) { .link-arrow { transition: none; } }
</style>
