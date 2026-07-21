<script lang="ts">
  import { AlertTriangle, ArrowRight, Loader2, RefreshCw } from "lucide-svelte";
  import { getSelectionChallenges } from "$lib/api";
  import type { SolutionPreview } from "$lib/types/job";
  import type {
    SelectionChallenge,
    SelectionChallengeLens,
    SelectionChallengeQuestion,
    SelectionChallengeSource,
    SelectionChallengeStaleReference,
  } from "$lib/types/selectionChallenge";
  import {
    SELECTION_CHALLENGE_ASSUMPTIONS,
    SELECTION_CHALLENGE_LENSES,
    SELECTION_CHALLENGE_QUESTION_LABELS,
    SELECTION_RISK_PRIORITY,
    selectionChallengeConsensusLabel,
  } from "$lib/utils/selectionRisk";
  import { solutionDisplayTitle } from "$lib/utils/solution-utils";

  interface RiskFocus {
    ideaId: string;
    ideaRevision: number;
    lens: SelectionChallengeLens;
    challengeId?: string;
    questionId?: string;
  }

  interface Props {
    jobId?: string;
    ideas: SolutionPreview[];
    onReviewGap: (focus: RiskFocus) => void;
  }

  type RiskRow = {
    idea: SolutionPreview;
    ideaIndex: number;
    lens: SelectionChallengeLens;
    challenge: SelectionChallenge | null;
    question: SelectionChallengeQuestion | null;
    kind: "risk" | "stale" | "unassessed" | "monitored";
    priority: number;
    checkedCount: number;
  };

  let { jobId, ideas, onReviewGap }: Props = $props();
  let challenges = $state<SelectionChallenge[]>([]);
  let stale = $state<SelectionChallengeStaleReference[]>([]);
  let loading = $state(false);
  let error = $state("");
  let loadedKey = "";

  function identity(idea: SolutionPreview): { id: string; revision: number } | null {
    if (!idea.idea_id || !Number.isInteger(idea.idea_revision) || Number(idea.idea_revision) < 1) return null;
    return { id: idea.idea_id, revision: Number(idea.idea_revision) };
  }

  function currentChallenges(idea: SolutionPreview): SelectionChallenge[] {
    const current = identity(idea);
    if (!current) return [];
    return challenges.filter((challenge) => (
      challenge.ideaId === current.id && challenge.ideaRevision === current.revision
    ));
  }

  function staleLenses(idea: SolutionPreview): SelectionChallengeLens[] {
    const current = identity(idea);
    if (!current) return [];
    return stale
      .filter((reference) => (
        reference.ideaId === current.id && reference.ideaRevision === current.revision
      ))
      .map((reference) => reference.lens);
  }

  function riskRows(): RiskRow[] {
    return ideas.map((idea, ideaIndex): RiskRow => {
      const saved = currentChallenges(idea);
      const candidates = saved.flatMap((challenge) => challenge.questions
        .filter((question) => question.consensus !== "supported")
        .map((question) => ({ challenge, question })));
      candidates.sort((left, right) => {
        const priority = SELECTION_RISK_PRIORITY[left.question.consensus]
          - SELECTION_RISK_PRIORITY[right.question.consensus];
        if (priority !== 0) return priority;
        return SELECTION_CHALLENGE_LENSES.findIndex((lens) => lens.value === left.challenge.lens)
          - SELECTION_CHALLENGE_LENSES.findIndex((lens) => lens.value === right.challenge.lens);
      });
      const top = candidates[0];
      if (top) {
        return {
          idea,
          ideaIndex,
          lens: top.challenge.lens,
          challenge: top.challenge,
          question: top.question,
          kind: "risk",
          priority: SELECTION_RISK_PRIORITY[top.question.consensus],
          checkedCount: saved.length,
        };
      }

      const staleLens = staleLenses(idea)[0];
      if (staleLens) {
        return {
          idea,
          ideaIndex,
          lens: staleLens,
          challenge: null,
          question: null,
          kind: "stale",
          priority: 5,
          checkedCount: saved.length,
        };
      }

      const unchecked = SELECTION_CHALLENGE_LENSES.find((lens) => (
        !saved.some((challenge) => challenge.lens === lens.value)
      ));
      return {
        idea,
        ideaIndex,
        lens: unchecked?.value ?? "demand",
        challenge: null,
        question: null,
        kind: unchecked ? "unassessed" : "monitored",
        priority: unchecked ? 6 : 7,
        checkedCount: saved.length,
      };
    }).sort((left, right) => left.priority - right.priority || left.ideaIndex - right.ideaIndex);
  }

  function citedSources(row: RiskRow): SelectionChallengeSource[] {
    if (!row.challenge || !row.question) return [];
    const keys = new Set([
      ...row.question.skeptic.evidenceKeys,
      ...row.question.auditor.evidenceKeys,
    ]);
    return row.challenge.evidenceSnapshot.filter((source) => keys.has(source.key));
  }

  function evidenceLabel(row: RiskRow): string {
    const sources = citedSources(row);
    if (!sources.length) return "No cited evidence";
    if (sources.some((source) => source.kind === "customer_quote")) return "Observed evidence cited";
    const experiment = sources.find((source) => source.kind === "experiment_result");
    if (experiment?.provenance.assetType === "EXPERIMENT_RESULT") {
      return experiment.provenance.evidenceClass === "observed"
        ? "Observed experiment cited"
        : "Owner-recorded experiment cited";
    }
    if (sources.some((source) => source.kind === "owner_evidence")) return "Owner input cited";
    return "Proxy evidence cited";
  }

  function lensLabel(lens: SelectionChallengeLens): string {
    return SELECTION_CHALLENGE_LENSES.find((item) => item.value === lens)?.label ?? lens;
  }

  function rowStatus(row: RiskRow): string {
    if (row.question?.consensus === "disputed") return "Assessments disagree";
    if (row.question?.consensus === "mixed") return "Mixed evidence";
    if (row.question) return selectionChallengeConsensusLabel(row.question.consensus);
    if (row.kind === "stale") return "Recheck needed";
    if (row.kind === "unassessed") return "Not assessed";
    return "No open gap";
  }

  function rowQuestion(row: RiskRow): string {
    if (row.question) {
      return SELECTION_CHALLENGE_QUESTION_LABELS[row.question.questionId] ?? row.question.questionId;
    }
    if (row.kind === "stale") return `${lensLabel(row.lens)} changed since the last evidence check.`;
    if (row.kind === "unassessed") return `${lensLabel(row.lens)} has not been independently checked.`;
    return "All four saved evidence lenses currently hold.";
  }

  function rowAssumption(row: RiskRow): string {
    if (row.question) {
      return SELECTION_CHALLENGE_ASSUMPTIONS[row.question.questionId]
        ?? row.question.skeptic.summary;
    }
    if (row.kind === "monitored") return "No unresolved question was found in the saved checks.";
    return `${row.checkedCount} of ${SELECTION_CHALLENGE_LENSES.length} lenses are current.`;
  }

  async function load() {
    if (!jobId) return;
    loading = true;
    error = "";
    try {
      const response = await getSelectionChallenges(jobId);
      challenges = response.challenges;
      stale = response.stale;
    } catch (cause) {
      error = cause instanceof Error ? cause.message : "Could not load decision risks.";
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    const revisions = ideas.map((idea) => `${idea.idea_id ?? ""}:${idea.idea_revision ?? ""}`).join("|");
    const key = `${jobId ?? ""}:${revisions}`;
    if (!jobId || key === loadedKey) return;
    loadedKey = key;
    void load();
  });
</script>

<section class="risk-queue" aria-labelledby="decision-risk-title">
  <header class="risk-head">
    <div>
      <p class="kicker">Biggest unknowns</p>
      <h3 id="decision-risk-title">What could change this decision?</h3>
      <p>One priority gap per compared idea. This orders what to learn next; it never changes research scores.</p>
    </div>
    {#if !loading && !error}
      <span class="risk-count">{riskRows().filter((row) => row.kind !== "monitored").length} unresolved</span>
    {/if}
  </header>

  {#if loading}
    <div class="queue-state" role="status"><Loader2 class="spin risk-spin" aria-hidden="true" /> Loading saved evidence checks…</div>
  {:else if error}
    <div class="queue-state queue-error" role="alert">
      <span>{error}</span>
      <button type="button" onclick={() => void load()}><RefreshCw aria-hidden="true" /> Retry</button>
    </div>
  {:else}
    <ol class="risk-list" role="list">
      {#each riskRows() as row, index (`${row.idea.idea_id}:${row.idea.idea_revision}`)}
        <li class:is-open={row.kind === "risk"}>
          <span class="risk-number">{String(index + 1).padStart(2, "0")}</span>
          <div class="risk-copy">
            <div class="risk-meta">
              <strong>{solutionDisplayTitle(row.idea)}</strong>
              <span>Evidence review · {lensLabel(row.lens)}</span>
            </div>
            <h4>{rowQuestion(row)}</h4>
            <p>{rowAssumption(row)}</p>
            {#if row.kind === "risk"}
              <small>{evidenceLabel(row)} · {row.checkedCount}/{SELECTION_CHALLENGE_LENSES.length} lenses checked</small>
            {/if}
          </div>
          <div class="risk-action">
            <span class="risk-status risk-status--{row.question?.consensus ?? row.kind}">
              {#if row.kind === "risk"}<AlertTriangle aria-hidden="true" />{/if}{rowStatus(row)}
            </span>
            {#if row.kind !== "monitored" && identity(row.idea)}
              {@const current = identity(row.idea)!}
              <button type="button" onclick={() => onReviewGap({
                ideaId: current.id,
                ideaRevision: current.revision,
                lens: row.lens,
                challengeId: row.challenge?.id,
                questionId: row.question?.questionId,
              })}>
                {row.kind === "risk" ? "Review gap" : "Open check"}<ArrowRight aria-hidden="true" />
              </button>
            {/if}
          </div>
        </li>
      {/each}
    </ol>
  {/if}

  <footer>Agent assessments are unresolved interpretations of captured evidence, not validation or a new score.</footer>
</section>

<style>
  .risk-queue {
    padding: 1.15rem 1.5rem 1rem;
    background: var(--color-bg-surface);
  }
  .risk-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1.5rem;
    padding-bottom: 0.9rem;
    border-bottom: 1px solid var(--color-border-emphasis);
  }
  .kicker {
    margin: 0 0 0.28rem;
    color: var(--color-accent-dark);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  h3, h4, p { margin: 0; }
  .risk-head h3 { font-size: var(--text-lg); line-height: 1.3; }
  .risk-head p {
    max-width: 47rem;
    margin-top: 0.32rem;
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: 1.5;
  }
  .risk-count {
    flex: 0 0 auto;
    padding-top: 0.15rem;
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-11);
    font-weight: 700;
  }
  .queue-state {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    min-height: 15rem;
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
  }
  .queue-state :global(svg) { width: 0.95rem; height: 0.95rem; }
  .queue-error { flex-direction: column; color: var(--color-error-text); }
  .queue-error button {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    min-height: 2.25rem;
    padding: 0.45rem 0.7rem;
    border: 1px solid var(--color-border-emphasis);
    border-radius: 0.5rem;
    background: var(--color-bg-elevated);
    color: var(--color-text-primary);
    font: inherit;
    font-weight: 700;
    cursor: pointer;
    transition: background var(--duration-fast) var(--ease-default), border-color var(--duration-fast) var(--ease-default);
  }
  .queue-error button:hover { background: var(--color-bg-hover); border-color: var(--color-text-secondary); }
  .queue-error button:active { background: var(--color-bg-hover); }
  .risk-list { margin: 0; padding: 0; list-style: none; }
  .risk-list li {
    display: grid;
    grid-template-columns: 2rem minmax(0, 1fr) minmax(8.5rem, auto);
    gap: 0.8rem;
    align-items: start;
    padding: 0.95rem 0;
    border-bottom: 1px solid var(--color-border);
  }
  .risk-list li.is-open { background: var(--color-bg-elevated); }
  .risk-number {
    padding-left: 0.5rem;
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
  }
  .risk-copy { min-width: 0; }
  .risk-meta { display: flex; flex-wrap: wrap; gap: 0.35rem 0.6rem; align-items: baseline; }
  .risk-meta strong { font-size: var(--text-sm); }
  .risk-meta span {
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
  }
  .risk-copy h4 { margin-top: 0.3rem; font-size: var(--text-base); line-height: 1.35; }
  .risk-copy p { margin-top: 0.28rem; color: var(--color-text-secondary); font-size: var(--text-sm); line-height: 1.48; }
  .risk-copy small { display: block; margin-top: 0.35rem; color: var(--color-text-secondary); font-size: var(--text-xs); }
  .risk-action { display: grid; justify-items: end; gap: 0.45rem; }
  .risk-status {
    display: inline-flex;
    align-items: center;
    gap: 0.28rem;
    color: var(--color-text-secondary);
    font-size: var(--text-xs);
    font-weight: 800;
  }
  .risk-status :global(svg) { width: 0.75rem; height: 0.75rem; }
  .risk-status--contradicted { color: var(--color-error-text); }
  .risk-status--disputed, .risk-status--mixed, .risk-status--stale { color: var(--color-warning-text); }
  .risk-status--insufficient, .risk-status--unassessed { color: var(--color-text-secondary); }
  .risk-status--monitored { color: var(--color-success-dark); }
  .risk-action button {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    min-height: 2.25rem;
    padding: 0;
    border: 0;
    background: transparent;
    color: var(--color-accent-dark);
    font: inherit;
    font-size: var(--text-11);
    font-weight: 800;
    cursor: pointer;
    transition: color var(--duration-fast) var(--ease-default);
  }
  .risk-action button:hover { color: var(--color-accent-hover); text-decoration: underline; }
  .risk-action button:active { transform: scale(0.98); }
  .risk-action button :global(svg) { width: 0.8rem; height: 0.8rem; transition: transform var(--duration-fast) var(--ease-default); }
  .risk-action button:hover :global(svg) { transform: translateX(2px); }
  .risk-action button:focus-visible, .queue-error button:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .risk-queue > footer { padding-top: 0.75rem; color: var(--color-text-secondary); font-size: var(--text-xs); }
  :global(.risk-spin) { animation: risk-spin 800ms linear infinite; }
  @keyframes risk-spin { to { transform: rotate(360deg); } }

  @media (max-width: 640px) {
    .risk-queue { padding: 1rem; }
    .risk-head { display: block; }
    .risk-count { display: block; margin-top: 0.55rem; }
    .risk-list li { grid-template-columns: 1.6rem minmax(0, 1fr); gap: 0.65rem; }
    .risk-action {
      grid-column: 2;
      justify-items: stretch;
    }
    .risk-status { justify-content: flex-start; }
    .risk-action button {
      justify-content: space-between;
      min-height: 2.75rem;
      width: 100%;
      border-top: 1px solid var(--color-border);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .risk-action button:active {
      transform: none;
    }
  }
</style>
