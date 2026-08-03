<script lang="ts">
  import type { DiscoveryVoteRationale } from "$lib/api";
  import type { SolutionPreview } from "$lib/types/job";
  import { buildCollaboratorFeedbackGroups } from "$lib/utils/collaboratorFeedback";
  import { solutionDisplayTitle } from "$lib/utils/solution-utils";
  import CollaboratorFeedback from "./CollaboratorFeedback.svelte";

  interface Props {
    jobId: string;
    completed?: boolean;
    solutions: SolutionPreview[];
    selectedNames?: string[];
    selectionRationale?: string | null;
    solutionVotes?: Record<string, number>;
    solutionVotesById?: Record<string, number>;
    voteRationales?: DiscoveryVoteRationale[];
  }

  let {
    jobId,
    completed = false,
    solutions,
    selectedNames = [],
    selectionRationale = null,
    solutionVotes = {},
    solutionVotesById = {},
    voteRationales = [],
  }: Props = $props();

  const feedbackGroups = $derived(buildCollaboratorFeedbackGroups(solutions, voteRationales));
  const voteRows = $derived.by(() => solutions.flatMap((solution) => {
    const count = solution.idea_id
      ? solutionVotesById[solution.idea_id] ?? solutionVotes[solution.solution_name] ?? 0
      : solutionVotes[solution.solution_name] ?? 0;
    return count > 0 ? [{ key: solution.idea_id ?? solution.solution_name, label: solutionDisplayTitle(solution), count }] : [];
  }));
  const collaboratorVoteCount = $derived(voteRows.reduce((total, row) => total + row.count, 0));
  // selectedNames persists working names (solution_name). Rows everywhere else — the vote
  // record below, compare, the risk record — are titled with the headline, so resolve each
  // saved name back to its candidate and title it the same way. A name that matches more
  // than one candidate stays as saved rather than picking a revision arbitrarily.
  const scopeTitles = $derived(selectedNames.map((name) => {
    const matches = solutions.filter((solution) => solution.solution_name === name);
    return matches.length === 1 ? solutionDisplayTitle(matches[0]) : name;
  }));
</script>

<section class="decision-record" aria-labelledby="decision-record-title">
  <header>
    <div>
      <p class="eyebrow">Selection decision record</p>
      <h2 id="decision-record-title">{completed ? "How the research scope was chosen" : "Scope locked for Deep Research"}</h2>
      <p>
        {completed
          ? "The saved shortlist, comparison, evidence checks, and planning notes remain available as the record behind this report."
          : "The saved shortlist and supporting decision work remain readable while Deep Research runs."}
      </p>
    </div>
    <a href={`/jobs/${jobId}/selection/compare`}>Review decision record <span aria-hidden="true">→</span></a>
  </header>

  {#if selectedNames.length > 0}
    <ul class="scope" aria-label="Ideas sent to Deep Research">
      {#each scopeTitles as title}<li>{title}</li>{/each}
    </ul>
  {/if}

  <div class="rationale-record">
    <h3>Selection note</h3>
    <p class:empty={!selectionRationale?.trim()}>
      {selectionRationale?.trim() || "No note was saved with this selection."}
    </p>
  </div>

  {#if voteRows.length > 0}
    <div class="vote-record" aria-label={`${collaboratorVoteCount} collaborator votes saved`}>
      <p>{collaboratorVoteCount} collaborator {collaboratorVoteCount === 1 ? "vote" : "votes"} saved with selection</p>
      <dl>
        {#each voteRows as row (row.key)}
          <div><dt>{row.label}</dt><dd>{row.count}</dd></div>
        {/each}
      </dl>
    </div>
  {/if}

  {#if feedbackGroups.length > 0}
    <CollaboratorFeedback groups={feedbackGroups} readOnly />
  {/if}
</section>

<style>
  .decision-record {
    display: grid;
    gap: var(--space-4);
    margin-top: var(--space-6);
    padding: var(--space-5);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-bg-elevated);
  }
  header { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-5); }
  header > div { min-width: 0; }
  .eyebrow { margin: 0 0 var(--space-1); color: var(--color-text-muted); font: 700 var(--text-xs)/var(--leading-tight) var(--font-mono); letter-spacing: var(--tracking-wider); text-transform: uppercase; }
  h2 { margin: 0; color: var(--color-text-primary); font-size: var(--text-xl); line-height: var(--leading-tight); text-wrap: balance; }
  header p:last-child { max-width: 68ch; margin: var(--space-2) 0 0; color: var(--color-text-secondary); font-size: var(--text-sm); line-height: var(--leading-normal); text-wrap: pretty; }
  header a { display: inline-flex; flex: 0 0 auto; align-items: center; gap: var(--space-1); min-height: var(--space-10); color: var(--color-accent-dark); font-size: var(--text-sm); font-weight: 700; text-decoration: none; }
  header a:hover { color: var(--color-accent-hover); text-decoration: underline; text-underline-offset: var(--space-1); }
  header a:active { transform: scale(0.98); }
  header a:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  .scope { display: flex; flex-wrap: wrap; gap: var(--space-2); margin: 0; padding: 0; list-style: none; }
  .scope li { padding: var(--space-1-5) var(--space-3); border: 1px solid var(--color-border); border-radius: 999px; color: var(--color-text-secondary); font-size: var(--text-xs); font-weight: 700; }
  .rationale-record { display: grid; gap: var(--space-1); padding-top: var(--space-3); border-top: 1px solid var(--color-border); }
  .rationale-record h3 { margin: 0; color: var(--color-text-primary); font-size: var(--text-sm); line-height: var(--leading-tight); }
  .rationale-record p { margin: 0; color: var(--color-text-secondary); font-size: var(--text-sm); line-height: var(--leading-normal); white-space: pre-wrap; }
  .rationale-record p.empty { color: var(--color-text-muted); }
  .vote-record { display: grid; gap: var(--space-2); padding-top: var(--space-3); border-top: 1px solid var(--color-border); }
  .vote-record > p { margin: 0; color: var(--color-text-secondary); font-size: var(--text-sm); }
  dl { display: flex; flex-wrap: wrap; gap: var(--space-2) var(--space-5); margin: 0; }
  dl div { display: flex; align-items: baseline; gap: var(--space-2); }
  dt { color: var(--color-text-secondary); font-size: var(--text-xs); }
  dd { margin: 0; color: var(--color-text-primary); font-family: var(--font-mono); font-size: var(--text-sm); font-variant-numeric: tabular-nums; font-weight: 700; }
  @media (max-width: 700px) {
    .decision-record { padding: var(--space-4); }
    header { flex-direction: column; gap: var(--space-2); }
    header a { min-height: 2.75rem; }
  }
  @media (prefers-reduced-motion: reduce) {
    header a:active { transform: none; }
  }
</style>
