<script lang="ts">
  import type { PageData } from "./$types";
  import Tooltip from "$lib/components/ui/Tooltip.svelte";
  import { HelpCircle } from "lucide-svelte";
  import {
    computeCompositeScore,
    originalityScore,
    solutionDisplayTitle,
  } from "$lib/utils/solution-utils";
  import { getWorkspaceTools } from "$lib/selection/workspaceTools";
  import { formatBuildConstraints } from "$lib/selection/profileFormat";

  let { data }: { data: PageData } = $props();

  const tools = getWorkspaceTools();

  function viewHref(view: "market" | "founder"): string {
    const params = new URLSearchParams(data.workspace.canonicalQuery.slice(1));
    params.set("view", view);
    return `?${params.toString()}`;
  }

  const metricMap = $derived(new Map(
    (data.metricExplanations?.metrics ?? []).map((metric) => [metric.key, metric]),
  ));

  function score(value: number | null | undefined): string {
    return typeof value === "number" ? `${Math.round(value * 100)}%` : "Not available";
  }

  function founderFitFor(ideaId: string | undefined, ideaRevision: number | undefined) {
    return data.founderFit?.analysis?.results.find((result) => (
      result.ideaId === ideaId && result.ideaRevision === (ideaRevision ?? 1)
    )) ?? null;
  }

  function profileSummary(): string {
    const profile = data.decisionState?.profile;
    if (!profile) return "No build constraints saved yet.";
    return formatBuildConstraints(profile);
  }

  function runFitAction(): void {
    if (data.decisionState?.profile) tools.openFit();
    else tools.openConstraints();
  }

  /** Index of the sole highest-scoring candidate in a row, or -1 on a tie or
   *  when there is nothing to compare — used to mark the row leader. */
  function leaderIndexOf(values: Array<number | null | undefined>): number {
    const nums = values.map((v, i) => ({ v, i })).filter((x): x is { v: number; i: number } => typeof x.v === "number");
    if (nums.length < 2) return -1;
    const max = Math.max(...nums.map((x) => x.v));
    const leaders = nums.filter((x) => x.v === max);
    return leaders.length === 1 ? leaders[0].i : -1;
  }

  function pct(v: number | null | undefined): number {
    return typeof v === "number" ? Math.round(v * 100) : 0;
  }

  type RowKind = "score" | "text" | "narrative";
  const marketRows = $derived.by(() => {
    const ideas = data.workspace.ideas;
    const col = <T,>(get: (i: (typeof ideas)[number]) => T) => ideas.map(get);
    const rows: Array<{ key: string; fallback: string; kind: RowKind; values: Array<number | string | null | undefined> }> = [
      { key: "research_score", fallback: "Research score", kind: "score", values: col(computeCompositeScore) },
      { key: "market_fit", fallback: "Market fit", kind: "score", values: col((i) => i.market_fit_score) },
      { key: "technical_feasibility", fallback: "Feasibility", kind: "score", values: col((i) => i.technical_feasibility_score) },
      { key: "distribution_seo", fallback: "Distribution / SEO", kind: "score", values: col((i) => i.seo_scalability_score) },
      { key: "originality", fallback: "Originality", kind: "score", values: col(originalityScore) },
      { key: "build_estimate", fallback: "Build estimate", kind: "text", values: col((i) => i.estimated_development_time ?? "Not available") },
      { key: "evidence_anchor", fallback: "Evidence anchor", kind: "narrative", values: col((i) => i.source_pain ?? i.pain_points_addressed?.[0] ?? "No direct pain anchor is available.") },
      { key: "audience", fallback: "Audience", kind: "narrative", values: col((i) => i.source_segment ?? i.target_personas?.[0] ?? "No audience anchor is available.") },
      { key: "distinctive_wedge", fallback: "Distinctive wedge", kind: "narrative", values: col((i) => i.differentiation_locus ?? i.innovation_angle ?? i.differentiation_factors?.[0] ?? i.value_proposition) },
      { key: "known_concern", fallback: "Known concern", kind: "narrative", values: col((i) => i.critic_concern ?? i.incumbent_parity ?? i.data_acquisition_notes ?? "No concern is recorded.") },
    ];
    return rows.map((row) => ({
      ...row,
      leaderIndex: row.kind === "score" ? leaderIndexOf(row.values as Array<number | null | undefined>) : -1,
    }));
  });
</script>

{#snippet metricLabel(key: string, fallback: string)}
  {@const explanation = metricMap.get(key)}
  <span class="metric-label-copy">{explanation?.label ?? fallback}</span>
  {#if explanation}
    <Tooltip content={`${explanation.summary} ${explanation.caveat ?? ""}`.trim()} position="right">
      {#snippet children()}
        <button type="button" class="metric-help" aria-label={`How ${explanation.label} is calculated`}>
          <HelpCircle aria-hidden="true" />
        </button>
      {/snippet}
    </Tooltip>
  {/if}
{/snippet}

<section class="selection-page">
  <header class="selection-page__header">
    <div>
      <h2>See what actually separates your shortlist</h2>
      <p class="selection-page__lead">
        Market evidence stays separate from your constraints. Switching views never changes a research score.
      </p>
    </div>
    <div class="selection-page__switcher" aria-label="Comparison view">
      <a class:active={data.workspace.compareView === "market"} href={viewHref("market")}>Market</a>
      <a class:active={data.workspace.compareView === "founder"} href={viewHref("founder")}>Your fit</a>
    </div>
  </header>

  {#if data.workspace.ideas.length < 2}
    <div class="selection-page__panel selection-page__empty">
      <div>
        <h3>Choose at least two candidates to compare</h3>
        <p>Return to the ranked list, shortlist another candidate, then reopen this workspace.</p>
        <a class="selection-page__link" href={`/jobs/${data.job.id}`}>Review ranked candidates <span aria-hidden="true">→</span></a>
      </div>
    </div>
  {:else}
    <div
      class="comparison selection-page__panel"
      style={`--candidate-count: ${Math.max(data.workspace.ideas.length, 1)}`}
    >
      <div class="comparison-label header-label">Candidate</div>
      {#each data.workspace.ideas as idea, index}
        <article class="candidate-heading">
          <small>
            Candidate {index + 1}{#if (idea.idea_revision ?? 1) > 1} · rev {idea.idea_revision}{/if}
          </small>
          <h3>{solutionDisplayTitle(idea)}</h3>
          <p>{idea.short_description ?? idea.description}</p>
        </article>
      {/each}

      {#if data.workspace.compareView === "market"}
        {#each marketRows as row (row.key)}
          <div class="comparison-label">{@render metricLabel(row.key, row.fallback)}</div>
          {#each row.values as v, i}
            <div
              class="comparison-value"
              class:metric-cell={row.kind === "score"}
              class:narrative={row.kind === "narrative"}
              class:is-leader={i === row.leaderIndex}
            >
              {#if row.kind === "score"}
                <span class="bar" aria-hidden="true"><span class="bar-fill" style={`width:${pct(v as number)}%`}></span></span>
                <span class="metric-num">{score(v as number)}</span>
                {#if i === row.leaderIndex}<span class="leads">Leads</span>{/if}
              {:else}
                {v}
              {/if}
            </div>
          {/each}
        {/each}
      {:else}
        <div class="comparison-label">Your saved lens</div>
        {#each data.workspace.ideas as idea}<div class="comparison-value narrative">{profileSummary()}</div>{/each}
        <div class="comparison-label">Fit verdict</div>
        {#each data.workspace.ideas as idea}<div class="comparison-value verdict">{founderFitFor(idea.idea_id, idea.idea_revision)?.verdict.replaceAll("_", " ") ?? "Not analyzed"}</div>{/each}
        <div class="comparison-label">Why it fits or does not</div>
        {#each data.workspace.ideas as idea}<div class="comparison-value narrative">{founderFitFor(idea.idea_id, idea.idea_revision)?.summary ?? "Analyze fit against your saved build constraints first."}</div>{/each}
        <div class="comparison-label">Strongest advantage</div>
        {#each data.workspace.ideas as idea}<div class="comparison-value narrative">{founderFitFor(idea.idea_id, idea.idea_revision)?.strongestAdvantage ?? "Not available"}</div>{/each}
        <div class="comparison-label">Blocking conflict</div>
        {#each data.workspace.ideas as idea}<div class="comparison-value narrative">{founderFitFor(idea.idea_id, idea.idea_revision)?.blockingConflict ?? "No blocking conflict recorded."}</div>{/each}
        <div class="comparison-label">Decision-changing unknown</div>
        {#each data.workspace.ideas as idea}<div class="comparison-value narrative">{founderFitFor(idea.idea_id, idea.idea_revision)?.decisionChangingUnknown ?? "This candidate still needs a fit analysis."}</div>{/each}
      {/if}
    </div>
    {#if data.workspace.compareView === "founder" && (!data.decisionState?.profile || !data.founderFit?.analysis || data.founderFit.stale)}
      <aside class="fit-action" aria-live="polite">
        <div>
          <strong>{!data.decisionState?.profile ? "Add your build constraints" : data.founderFit?.stale ? "Your fit analysis is out of date" : "Analyze fit for you"}</strong>
          <p>{!data.decisionState?.profile
            ? "Save your available time, testing budget, team, and advantages before comparing personal fit."
            : "The market scores stay unchanged; this analysis only checks each idea against your situation."}</p>
        </div>
        <button type="button" onclick={runFitAction}>{!data.decisionState?.profile ? "Add constraints" : "Open fit analysis"} <span aria-hidden="true">→</span></button>
      </aside>
    {/if}
  {/if}
</section>

<style>
  /* Scorecard, not spreadsheet: horizontal row separators only (no vertical
     grid lines), a highlighted leader per numeric row, and value bars so
     differences read at a glance. All colors are tokens. */
  .comparison {
    display: grid;
    grid-template-columns: minmax(9rem, 0.6fr) repeat(var(--candidate-count, 2), minmax(0, 1fr));
    overflow: hidden;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-bg-elevated);
  }
  .comparison > * { min-width: 0; padding: 0.75rem 1rem; border-bottom: 1px solid var(--color-border); }

  .header-label { color: var(--color-text-muted); font: 700 var(--text-11)/1.2 var(--font-mono); letter-spacing: 0.1em; text-transform: uppercase; }
  .candidate-heading { padding-top: 1rem; padding-bottom: 1rem; background: var(--color-bg-surface); }
  .candidate-heading small { color: var(--color-text-muted); font: 700 var(--text-xs)/1.2 var(--font-mono); letter-spacing: 0.12em; text-transform: uppercase; }
  .candidate-heading h3 { margin: 0.5rem 0 0; font-family: var(--font-display); font-size: var(--text-md); font-weight: 700; line-height: 1.3; letter-spacing: -0.01em; }
  .candidate-heading p { display: -webkit-box; overflow: hidden; margin: 0.4rem 0 0; color: var(--color-text-secondary); font-size: var(--text-13); line-height: 1.45; -webkit-box-orient: vertical; -webkit-line-clamp: 2; line-clamp: 2; }

  .comparison-label { display: flex; gap: 0.375rem; align-items: center; color: var(--color-text-secondary); font-size: var(--text-13); font-weight: 700; }
  .metric-label-copy { min-width: 0; }
  .metric-help { display: grid; flex: 0 0 auto; width: 1.5rem; height: 1.5rem; padding: 0; place-items: center; border: 0; border-radius: 50%; color: var(--color-text-muted); background: transparent; cursor: help; transition: color var(--duration-fast) var(--ease-default), background var(--duration-fast) var(--ease-default); }
  .metric-help:hover { color: var(--color-text-secondary); background: var(--color-bg-surface); }
  .metric-help :global(svg) { width: 0.85rem; height: 0.85rem; }
  .metric-help:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }

  .comparison-value { color: var(--color-text-primary); font-size: var(--text-base); font-weight: 600; }

  /* Numeric metric: a bar + the value. The row leader reads via WEIGHT + a dark
     bar + one accent "Leads" chip — a single brand-orange signal, not three. */
  .metric-cell { display: flex; align-items: center; gap: 0.5rem; }
  .bar { flex: 1; min-width: 2rem; max-width: 7rem; height: 0.375rem; border-radius: 999px; background: var(--color-bg-surface); box-shadow: inset 0 0 0 1px var(--color-border); overflow: hidden; }
  .bar-fill { display: block; height: 100%; border-radius: 999px; background: var(--color-text-muted); }
  .metric-num { flex: 0 0 auto; min-width: 2.75rem; font-variant-numeric: tabular-nums; font-weight: 600; color: var(--color-text-secondary); }
  .is-leader .bar-fill { background: var(--color-text-primary); }
  .is-leader .metric-num { color: var(--color-text-primary); font-weight: 800; }
  .leads { flex: 0 0 auto; padding: 0.125rem 0.375rem; border-radius: 999px; background: var(--color-accent-subtle); color: var(--color-accent-dark); font: 700 var(--text-xs)/1.3 var(--font-mono); letter-spacing: 0.06em; text-transform: uppercase; }

  .verdict { text-transform: capitalize; }
  .narrative { color: var(--color-text-secondary); font-size: var(--text-13); font-weight: 400; line-height: 1.5; }

  .fit-action { display: flex; justify-content: space-between; gap: 1rem; align-items: center; margin-top: 1rem; padding: 0.875rem 1rem; border: 1px solid var(--color-border-accent); border-radius: var(--radius-lg); background: var(--color-accent-subtle); }
  .fit-action strong, .fit-action p { display: block; margin: 0; }
  .fit-action strong { font-size: var(--text-base); }
  .fit-action p { margin-top: 0.2rem; color: var(--color-text-secondary); font-size: var(--text-13); line-height: 1.45; }
  .fit-action button { flex: 0 0 auto; min-height: 1.75rem; padding: 0.25rem 0; border: 0; background: transparent; color: var(--color-accent-dark); font: inherit; font-size: var(--text-base); font-weight: 700; cursor: pointer; }
  .fit-action button:hover { text-decoration: underline; text-underline-offset: 0.2rem; }
  .fit-action button:active { transform: scale(0.98); }

  @media (max-width: 767px) {
    .comparison { display: block; }
    .comparison-label { background: var(--color-bg-surface); }
    .bar { max-width: none; }
    .fit-action { align-items: flex-start; flex-direction: column; }
  }
</style>
