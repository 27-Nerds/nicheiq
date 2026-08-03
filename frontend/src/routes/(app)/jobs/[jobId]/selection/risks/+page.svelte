<script lang="ts">
  import { goto, invalidateAll, replaceState } from "$app/navigation";
  import { page } from "$app/state";
  import { getContext, tick } from "svelte";
  import type { PageData } from "./$types";
  import AssumptionMap from "$lib/components/selection/AssumptionMap.svelte";
  import EvidenceChallenge from "$lib/components/selection/EvidenceChallenge.svelte";
  import ExperimentWorkspace from "$lib/components/selection/ExperimentWorkspace.svelte";
  import {
    discardOwnerEvidenceDraft,
    ownerEvidenceDraftIsDirty,
  } from "$lib/components/selection/OwnerEvidenceLedger.svelte";
  import SegmentControl from "$lib/components/ui/SegmentControl.svelte";
  import Button from "$lib/components/ui/Button.svelte";
  import EmptyState from "$lib/components/ui/EmptyState.svelte";
  import { EVIDENCE_CHECK_EYEBROW } from "$lib/selection/labels";
  import { getWorkspaceTools, workspaceIdeaKey } from "$lib/selection/workspaceTools";
  import type {
    SelectionAssumptionPrefill,
    SelectionOwnerEvidencePrefill,
  } from "$lib/types/selectionCopilot";
  import type { SelectionChallengeLens } from "$lib/types/selectionChallenge";
  import { solutionDisplayTitle } from "$lib/utils/solution-utils";
  import {
    SELECTION_LIFECYCLE_CONTEXT,
    type SelectionWorkspaceLifecycle,
  } from "../selectionWorkspace";

  let { data }: { data: PageData } = $props();

  const tools = getWorkspaceTools();
  const lifecycle = getContext<SelectionWorkspaceLifecycle | undefined>(SELECTION_LIFECYCLE_CONTEXT);
  const currentStatus = $derived(lifecycle?.status || data.job.status);
  const canMutate = $derived(lifecycle?.status ? lifecycle.canMutate : currentStatus === "AWAITING_SELECTION");
  const validLenses: SelectionChallengeLens[] = [
    "demand",
    "distribution",
    "competition",
    "dependencies",
  ];

  let assumptionPrefill = $state<SelectionAssumptionPrefill | null>(null);
  let ownerEvidencePrefill = $state<SelectionOwnerEvidencePrefill | null>(null);
  let evidenceWorkspaceEl = $state<HTMLDivElement | null>(null);
  let proofRegionEl = $state<HTMLElement | null>(null);
  let savedTestsOpen = $state(false);
  let savedTestsEl = $state<HTMLDetailsElement | null>(null);
  let handledProofFocus = "";

  function revealEvidenceCheck(): void {
    evidenceWorkspaceEl?.scrollIntoView({ block: "start" });
  }

  function revealLinkedTest(): void {
    savedTestsOpen = true;
    void tick().then(() => savedTestsEl?.scrollIntoView({ behavior: "smooth", block: "start" }));
  }
  let handledAssumptionPrefill = "";
  let handledOwnerEvidencePrefill = "";

  const requestedIdeaId = $derived(page.url.searchParams.get("ideaId"));
  const requestedIdeaRevision = $derived(Number(page.url.searchParams.get("ideaRevision") ?? "1"));
  const focusedIdea = $derived(
    data.workspace.ideas.find((idea) => (
      idea.idea_id === requestedIdeaId
      && (idea.idea_revision ?? 1) === requestedIdeaRevision
    )) ?? data.workspace.ideas[0] ?? null,
  );
  const activeLens = $derived(
    validLenses.includes(page.url.searchParams.get("lens") as SelectionChallengeLens)
      ? page.url.searchParams.get("lens") as SelectionChallengeLens
      : data.workspace.lens,
  );
  const experimentStateKey = $derived(JSON.stringify(data.decisionState?.experiments ?? []));
  const focusRequestId = $derived(hashFocus(
    [
      focusedIdea?.idea_id ?? "",
      focusedIdea?.idea_revision ?? 1,
      activeLens,
      page.url.searchParams.get("challengeId") ?? "",
      page.url.searchParams.get("questionId") ?? "",
    ].join(":"),
  ));
  const challengeFocus = $derived(
    focusedIdea?.idea_id
      ? {
          requestId: focusRequestId,
          ideaId: focusedIdea.idea_id,
          ideaRevision: focusedIdea.idea_revision ?? 1,
          lens: activeLens,
          challengeId: page.url.searchParams.get("challengeId") ?? undefined,
          questionId: page.url.searchParams.get("questionId") ?? undefined,
        }
      : null,
  );

  function hashFocus(value: string): number {
    let hash = 0;
    for (let index = 0; index < value.length; index += 1) {
      hash = ((hash << 5) - hash + value.charCodeAt(index)) | 0;
    }
    return Math.abs(hash) || 1;
  }

  function focusedHref(
    ideaId: string,
    ideaRevision: number,
    lens = activeLens,
    focus?: "proof",
  ): string {
    const params = new URLSearchParams(data.workspace.canonicalQuery.slice(1));
    params.set("ideaId", ideaId);
    params.set("ideaRevision", String(ideaRevision));
    params.set("lens", lens);
    for (const key of ["tool", "assumptionId", "challengeId", "questionId"]) params.delete(key);
    if (focus) params.set("focus", focus);
    else params.delete("focus");
    return `/jobs/${data.job.id}/selection/risks?${params.toString()}`;
  }

  function updateFocus(lens: SelectionChallengeLens): void {
    if (!focusedIdea?.idea_id) return;
    void goto(
      focusedHref(
        focusedIdea.idea_id,
        focusedIdea.idea_revision ?? 1,
        lens,
        page.url.searchParams.get("focus") === "proof" ? "proof" : undefined,
      ),
      { replaceState: true, noScroll: true, keepFocus: true },
    );
  }

  function returnToEvidenceDraft(target: {
    jobId: string;
    ideaId: string;
    ideaRevision: number;
    lens: SelectionChallengeLens;
  }): void {
    if (target.jobId !== data.job.id) return;
    void goto(focusedHref(target.ideaId, target.ideaRevision, target.lens), {
      replaceState: true,
      noScroll: true,
    });
  }

  const candidateOptions = $derived(
    data.workspace.ideas
      .filter((idea) => idea.idea_id)
      .map((idea, index) => ({
        value: workspaceIdeaKey(idea),
        label: `${solutionDisplayTitle(idea)} · idea ${index + 1}`,
      })),
  );
  // Bound so a cancelled switch can snap the control back to the focused idea.
  let candidateKey = $state("");
  let pendingCandidateKey = $state("");
  $effect(() => {
    candidateKey = focusedIdea ? workspaceIdeaKey(focusedIdea) : "";
  });
  function changeCandidate(key: string): void {
    const idea = data.workspace.ideas.find((candidate) => workspaceIdeaKey(candidate) === key);
    if (!idea?.idea_id) return;
    const evidenceDraftIsDirty = ownerEvidenceDraftIsDirty();
    if (evidenceDraftIsDirty) {
      pendingCandidateKey = key;
      candidateKey = focusedIdea ? workspaceIdeaKey(focusedIdea) : "";
      return;
    }
    discardOwnerEvidenceDraft();
    void goto(focusedHref(idea.idea_id, idea.idea_revision ?? 1), {
      replaceState: true,
      noScroll: true,
      keepFocus: true,
    });
  }

  function cancelCandidateSwitch(): void {
    pendingCandidateKey = "";
    candidateKey = focusedIdea ? workspaceIdeaKey(focusedIdea) : "";
  }

  function confirmCandidateSwitch(): void {
    const idea = data.workspace.ideas.find(
      (candidate) => workspaceIdeaKey(candidate) === pendingCandidateKey,
    );
    if (!idea?.idea_id) {
      cancelCandidateSwitch();
      return;
    }
    pendingCandidateKey = "";
    candidateKey = workspaceIdeaKey(idea);
    void goto(focusedHref(idea.idea_id, idea.idea_revision ?? 1), {
      replaceState: true,
      noScroll: true,
      keepFocus: true,
    });
  }

  function trackRisk(prefill: SelectionAssumptionPrefill): void {
    if (!canMutate) return;
    assumptionPrefill = prefill;
  }

  function clearNavigationState(key: "selectionAssumptionPrefill" | "selectionOwnerEvidencePrefill"): void {
    replaceState(`${page.url.pathname}${page.url.search}`, {
      ...page.state,
      [key]: undefined,
    });
  }

  $effect(() => {
    const prefill = page.state.selectionAssumptionPrefill;
    if (!canMutate || !prefill || prefill.requestId === handledAssumptionPrefill) return;
    handledAssumptionPrefill = prefill.requestId;
    queueMicrotask(() => {
      assumptionPrefill = prefill;
      clearNavigationState("selectionAssumptionPrefill");
    });
  });

  $effect(() => {
    const prefill = page.state.selectionOwnerEvidencePrefill;
    if (!canMutate || !prefill || prefill.requestId === handledOwnerEvidencePrefill) return;
    handledOwnerEvidencePrefill = prefill.requestId;
    queueMicrotask(() => {
      ownerEvidencePrefill = prefill;
      clearNavigationState("selectionOwnerEvidencePrefill");
    });
  });

  $effect(() => {
    if (page.url.searchParams.get("focus") !== "proof") {
      handledProofFocus = "";
      return;
    }
    const focusKey = `${focusedIdea?.idea_id ?? ""}@${focusedIdea?.idea_revision ?? 1}`;
    if (!proofRegionEl || handledProofFocus === focusKey) return;
    handledProofFocus = focusKey;
    queueMicrotask(() => proofRegionEl?.scrollIntoView?.({ block: "start" }));
  });
</script>

<section class="evidence-page">
  <header class="page-intro" data-tour="evidence-intro">
    <p class="eyebrow">{EVIDENCE_CHECK_EYEBROW}</p>
    <h2>{canMutate ? "Check the evidence before you spend credits" : "Evidence and risk record"}</h2>
    <p>{canMutate
      ? "Choose the question most likely to change your shortlist. Each check rereads saved evidence only and never changes a score."
      : "Saved evidence checks, owner evidence, unresolved questions, and test plans from the selection decision. This record cannot be changed."}</p>
  </header>

  {#if focusedIdea}
    <nav class="candidate-switcher" aria-label="Candidate to review">
      <span id="risk-candidate-label">Review idea</span>
      <SegmentControl
        options={candidateOptions}
        bind:value={candidateKey}
        density="compact"
        label="Candidate to review"
        labelledBy="risk-candidate-label"
        onChange={changeCandidate}
      />
    </nav>
    {#if pendingCandidateKey}
      {@const pendingCandidate = data.workspace.ideas.find(
        (candidate) => workspaceIdeaKey(candidate) === pendingCandidateKey,
      )}
      <section class="candidate-switch-confirm" role="alert" aria-labelledby="candidate-switch-title">
        <div>
          <strong id="candidate-switch-title">Switch candidates?</strong>
          <p>
            Your unsaved evidence stays attached to
            {focusedIdea ? solutionDisplayTitle(focusedIdea) : "this candidate"}.
            {#if pendingCandidate} You are switching to {solutionDisplayTitle(pendingCandidate)}.{/if}
          </p>
        </div>
        <div class="candidate-switch-confirm__actions">
          <button type="button" onclick={cancelCandidateSwitch}>Stay here</button>
          <button type="button" class="confirm" onclick={confirmCandidateSwitch}>
            Switch and keep draft
          </button>
        </div>
      </section>
    {/if}

    <div class="evidence-workspace" bind:this={evidenceWorkspaceEl}>
      <EvidenceChallenge
        jobId={data.job.id}
        ideas={[focusedIdea]}
        focus={challengeFocus}
        onLensChange={updateFocus}
        onTrackRisk={trackRisk}
        onBranchDirection={() => tools.openVariants()}
        {ownerEvidencePrefill}
        onReturnToEvidenceDraft={returnToEvidenceDraft}
        onChanged={() => { void invalidateAll(); }}
        disabled={!canMutate}
      />
    </div>

    <section class="proof-region" bind:this={proofRegionEl}>
      <AssumptionMap
        jobId={data.job.id}
        ideas={[focusedIdea]}
        prefill={assumptionPrefill}
        onTestUnknown={(draft) => tools.openTestPlanner({
          ideaId: draft.ideaId,
          ideaRevision: draft.ideaRevision,
          assumptionId: draft.assumptionId ?? undefined,
          draft,
        })}
        onChanged={async () => { await invalidateAll(); }}
        onOpenLinkedTest={revealLinkedTest}
        disabled={!canMutate}
      />
    </section>

    {#if (data.decisionState?.experiments.length ?? 0) > 0}
      <details class="saved-tests" bind:open={savedTestsOpen} bind:this={savedTestsEl}>
        <summary>
          <span>Saved test plans</span>
          <small>{data.decisionState?.experiments.length} saved</small>
        </summary>
        {#key experimentStateKey}
          <ExperimentWorkspace
            surface="page"
            jobId={data.job.id}
            ideas={data.workspace.ideas}
            onOpenChallenge={revealEvidenceCheck}
            onChanged={() => { void invalidateAll(); }}
            disabled={!canMutate}
          />
        {/key}
      </details>
    {/if}
  {:else}
    <div class="empty">
      <EmptyState
        title="No candidate is in scope"
        description={canMutate
          ? "Choose a current idea revision before checking its evidence."
          : "No current idea revision is available in this saved decision record."}
      >
        <Button href={`/jobs/${data.job.id}`} class="btn-ghost" label="Back to ranked ideas" />
      </EmptyState>
    </div>
  {/if}
</section>

<style>
  .evidence-page { display: grid; gap: var(--space-6); }
  .page-intro { max-width: 58rem; }
  .eyebrow {
    margin: 0 0 var(--space-2);
    color: var(--color-text-muted);
    font: 700 var(--text-xs)/var(--leading-tight) var(--font-mono);
    letter-spacing: var(--tracking-wider);
    text-transform: uppercase;
  }
  .page-intro h2 {
    max-width: 28ch;
    margin: 0;
    font-family: var(--font-display);
    font-size: var(--text-4xl);
    font-weight: 700;
    line-height: var(--leading-tight);
    letter-spacing: var(--tracking-tight);
    text-wrap: balance;
  }
  .saved-tests {
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-bg-elevated);
    overflow: clip;
  }
  .saved-tests > summary {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-4);
    min-height: var(--space-12);
    padding: var(--space-3) var(--space-4);
    color: var(--color-text-primary);
    font-size: var(--text-base);
    font-weight: 700;
    cursor: pointer;
  }
  .saved-tests > summary:hover { background: var(--color-bg-surface); }
  .saved-tests > summary:active { background: var(--color-bg-hover); }
  .saved-tests > summary small {
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: var(--tracking-wide);
    text-transform: uppercase;
  }
  .saved-tests[open] > summary { border-bottom: 1px solid var(--color-border); }
  .page-intro > p:last-child {
    max-width: 66ch;
    margin: var(--space-2) 0 0;
    color: var(--color-text-secondary);
    font-size: var(--text-md);
    line-height: var(--leading-normal);
  }

  .candidate-switcher {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: var(--space-3);
    align-items: center;
    padding-block: var(--space-2);
    border-block: 1px solid var(--color-border);
  }
  .candidate-switcher > span {
    color: var(--color-text-muted);
    font: 700 var(--text-xs)/var(--leading-tight) var(--font-mono);
    letter-spacing: var(--tracking-wider);
    text-transform: uppercase;
    white-space: nowrap;
  }
  .candidate-switch-confirm {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-4);
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--color-border-emphasis);
    border-radius: var(--radius-md);
    background: var(--color-bg-elevated);
  }
  .candidate-switch-confirm strong { color: var(--color-text-primary); }
  .candidate-switch-confirm p {
    margin: var(--space-1) 0 0;
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    line-height: var(--leading-snug);
  }
  .candidate-switch-confirm__actions {
    display: flex;
    flex: 0 0 auto;
    gap: var(--space-2);
  }
  .candidate-switch-confirm button {
    min-height: var(--space-10);
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-bg-elevated);
    color: var(--color-text-primary);
    font: inherit;
    font-size: var(--text-13);
    font-weight: 700;
    cursor: pointer;
  }
  .candidate-switch-confirm button.confirm {
    border-color: var(--color-accent-dark);
    background: var(--color-accent-dark);
    color: var(--color-text-on-accent);
  }
  .candidate-switch-confirm button:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .evidence-workspace { min-width: 0; }
  .proof-region {
    padding-top: var(--space-6);
    border-top: 1px solid var(--color-border-emphasis);
  }

  .empty {
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-bg-elevated);
  }

  @media (max-width: 767px) {
    .evidence-page { gap: var(--space-5); }
    .candidate-switcher { grid-template-columns: 1fr; }
    .candidate-switch-confirm { align-items: stretch; flex-direction: column; }
    .candidate-switch-confirm__actions { display: grid; grid-template-columns: 1fr; }
  }
</style>
