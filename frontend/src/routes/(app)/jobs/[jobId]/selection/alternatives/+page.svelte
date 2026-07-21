<script lang="ts">
  import type { PageData } from "./$types";
  import { solutionDisplayTitle } from "$lib/utils/solution-utils";
  import { getWorkspaceTools } from "$lib/selection/workspaceTools";
  let { data }: { data: PageData } = $props();

  const tools = getWorkspaceTools();

  const modes = [
    { key: "recommended", label: "Recommended", detail: "Let the evidence choose the angle" },
    { key: "novelty", label: "More distinct", detail: "Push the mechanism or buyer apart" },
    { key: "distribution", label: "Easier to reach", detail: "Start from an accessible channel" },
  ] as const;

  function modeHref(mode: (typeof modes)[number]["key"]): string {
    const params = new URLSearchParams(data.workspace.canonicalQuery.slice(1));
    params.set("mode", mode);
    return `?${params.toString()}`;
  }

</script>

<section class="selection-page">
  <header class="selection-page__header">
    <div>
      <h2>Branch without changing the original ideas</h2>
      <p class="selection-page__lead">New directions keep exact parent revisions. Their scores and conclusions never transfer automatically.</p>
    </div>
  </header>

  <div class="mode-grid" aria-label="Alternative direction">
    {#each modes as mode}
      <a class:active={data.workspace.alternativeMode === mode.key} href={modeHref(mode.key)}>
        <span>{mode.label}</span>
        <small>{mode.detail}</small>
      </a>
    {/each}
  </div>

  <div class="alternative-panel selection-page__panel">
    <div>
      <p class="panel-eyebrow">Exact parents</p>
      <h3>{data.workspace.ideas.length === 0 ? "Choose candidates to branch" : `Explore from ${data.workspace.ideas.length} current ${data.workspace.ideas.length === 1 ? "candidate" : "candidates"}`}</h3>
      <p>Use the existing generation flow to review deliberately different variants before evaluating or shortlisting one.</p>
    </div>
    <div class="parents">
      {#each data.workspace.ideas as idea}
        <article>
          {#if (idea.idea_revision ?? 1) > 1}
            <span>rev {idea.idea_revision}</span>
          {/if}
          <h4>{solutionDisplayTitle(idea)}</h4>
          <p>{idea.source_pain ?? idea.short_description ?? idea.description}</p>
        </article>
      {/each}
    </div>
    <button
      type="button"
      class="selection-page__link"
      disabled={data.workspace.ideas.length === 0}
      onclick={() => tools.openVariants()}
    >Explore variants <span class="link-arrow" aria-hidden="true">→</span></button>
  </div>
</section>

<style>
  .mode-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.5rem; margin-bottom: 1rem; }
  .mode-grid a { padding: 0.75rem; border-radius: var(--radius-md); background: var(--color-bg-surface); color: var(--color-text-secondary); text-decoration: none; transition: background var(--duration-fast) var(--ease-default), box-shadow var(--duration-fast) var(--ease-default), transform var(--duration-fast) var(--ease-default); }
  .mode-grid a:hover { box-shadow: inset 0 0 0 1px var(--color-border-emphasis); }
  .mode-grid a:active { transform: scale(0.99); }
  .mode-grid a.active { background: var(--color-accent-subtle); color: var(--color-accent-dark); box-shadow: inset 0 0 0 1px var(--color-border-accent); }
  .mode-grid span, .mode-grid small { display: block; }
  .mode-grid span { font-weight: 700; font-size: var(--text-base); }
  .mode-grid small { margin-top: 0.25rem; font-size: var(--text-sm); line-height: 1.35; }
  .alternative-panel { padding: 1.25rem; }
  .panel-eyebrow { margin: 0; color: var(--color-accent-dark); font: 700 var(--text-11)/1.3 var(--font-mono); letter-spacing: 0.12em; text-transform: uppercase; }
  .alternative-panel h3 { margin: 0.375rem 0 0; font-family: var(--font-display); font-size: var(--text-xl); }
  .alternative-panel > div > p { max-width: 60ch; margin: 0.5rem 0 0; color: var(--color-text-secondary); font-size: var(--text-13); line-height: 1.5; }
  .parents { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.75rem; margin-top: 1rem; }
  .parents article { padding: 0.75rem; border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-bg-surface); }
  .parents span { color: var(--color-text-muted); font: 700 var(--text-xs)/1.2 var(--font-mono); text-transform: uppercase; }
  .parents h4 { margin: 0.375rem 0 0; font-size: var(--text-base); }
  .parents p { margin: 0.375rem 0 0; color: var(--color-text-secondary); font-size: var(--text-13); line-height: 1.45; }
  .link-arrow { display: grid; width: 1.6rem; height: 1.6rem; place-items: center; border-radius: 50%; background: var(--color-accent-subtle); transition: transform 220ms cubic-bezier(0.32, 0.72, 0, 1); }
  .selection-page__link:hover:not(:disabled) .link-arrow { transform: translateX(0.2rem); }
  @media (max-width: 767px) { .mode-grid, .parents { grid-template-columns: 1fr; } }
  @media (prefers-reduced-motion: reduce) { .link-arrow, .mode-grid a, .mode-grid a:active { transition: none; transform: none; } }
</style>
