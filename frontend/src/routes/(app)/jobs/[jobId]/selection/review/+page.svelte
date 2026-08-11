<script lang="ts">
  import { goto, invalidateAll } from "$app/navigation";
  import { getContext } from "svelte";
  import type { PageData } from "./$types";
  import { ApiError, selectSolution } from "$lib/api";
  import type { SolutionPreview } from "$lib/types/job";
  import { displayCompositeScore, solutionDisplayTitle } from "$lib/utils/solution-utils";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";
  import Button from "$lib/components/ui/Button.svelte";
  import Badge from "$lib/components/ui/Badge.svelte";
  import FormField from "$lib/components/ui/FormField.svelte";
  import EmptyState from "$lib/components/ui/EmptyState.svelte";
  import SolutionDetail from "$lib/components/SolutionDetail.svelte";
  import { nonNegativeInteger } from "$lib/utils/displayGuards";
  import {
    SELECTION_LIFECYCLE_CONTEXT,
    type SelectionWorkspaceLifecycle,
  } from "../selectionWorkspace";
  import {
    guideRecordLine,
    CHOOSE_IDEAS_LABEL,
    TOOL_NAMES,
    STRESS_TEST_EVIDENCE_LABEL,
  } from "$lib/selection/labels";
  import { shortlistOverlaps, overlapWarningText } from "$lib/selection/overlapWarnings";
  import { rankedIdeasHref } from "$lib/selection/rankedIdeas";

  let { data }: { data: PageData } = $props();

  /** Admin-granted optional decision tools; the risk-check summary is one of them.
   *  /selection/review itself is never gated — only this block inside it. */
  const decisionTools = $derived(data.decisionTools === true);

  const lifecycle = getContext<SelectionWorkspaceLifecycle | undefined>(SELECTION_LIFECYCLE_CONTEXT);
  const currentStatus = $derived(lifecycle?.status || data.job.status);
  const canMutate = $derived(lifecycle?.status ? lifecycle.canMutate : currentStatus === "AWAITING_SELECTION");

  // Rationale survives navigation away from the commit gate: write-through to
  // sessionStorage per job, restored on mount, cleared after a successful start.
  const rationaleStorageKey = $derived(`nicheiq:research-rationale:${data.job.id}`);
  function restoreRationale(): string {
    if (typeof sessionStorage === "undefined") return "";
    try {
      return sessionStorage.getItem(rationaleStorageKey) ?? "";
    } catch {
      return "";
    }
  }
  let rationale = $state("");
  let rationaleJobId = $state("");
  let submitting = $state(false);
  let submitError = $state("");
  let clientRequestId = $state(crypto.randomUUID());
  let confirmationMismatch = $state<{
    previousIdeas: string[];
    previousCost: number | null;
    kind: "scope" | "cost" | "scope_and_cost";
  } | null>(null);
  let mismatchAcknowledged = $state(false);
  let mismatchHeading = $state<HTMLHeadingElement>();
  /** Index into the shortlist of the idea open in the read-only detail overlay.
   *  Inspecting an idea at the gate must not offer a select control — the
   *  shortlist is edited in Compare — so this opens with lifecycle="reference". */
  let detailIndex = $state<number | null>(null);

  $effect(() => {
    if (rationaleJobId === data.job.id) return;
    rationaleJobId = data.job.id;
    rationale = canMutate ? restoreRationale() : data.job.selectionRationale ?? "";
  });

  $effect(() => {
    if (rationaleJobId !== data.job.id) return;
    if (!canMutate) {
      rationale = data.job.selectionRationale ?? "";
      return;
    }
    const value = rationale;
    try {
      if (value) sessionStorage.setItem(rationaleStorageKey, value);
      else sessionStorage.removeItem(rationaleStorageKey);
    } catch {
      // Storage unavailable (private mode/quota) — the field still works page-locally.
    }
  });

  const selectedIdeas = $derived(data.workspace.ideas);
  const selectedCount = $derived(selectedIdeas.length);
  const selectedRefs = $derived(new Set(selectedIdeas.map((idea) => `${idea.idea_id}:${idea.idea_revision ?? 1}`)));
  const fitReferences = $derived(selectedIdeas.flatMap((idea) => (
    idea.idea_id
      ? [{ ideaId: idea.idea_id, ideaRevision: idea.idea_revision ?? 1 }]
      : []
  )));
  const fitResults = $derived(scopedFounderFitResults(data.founderFit, fitReferences));
  // Last chance to notice two shortlisted ideas are the same product. Deep Research
  // funds three slots and this gate is the only one that charges for them.
  const overlapWarnings = $derived(
    shortlistOverlaps(
      data.overlapGroups,
      selectedIdeas.map((idea) => ({
        name: idea.solution_name,
        label: solutionDisplayTitle(idea),
      })),
    ),
  );
  const savedRefs = $derived(new Set(
    recordArray(data.decisionState?.shortlist?.items)
      .map(referenceKey)
      .filter((reference): reference is string => reference !== null),
  ));
  const scopeMatchesSaved = $derived(
    selectedRefs.size === savedRefs.size && [...selectedRefs].every((reference) => savedRefs.has(reference)),
  );
  const decisionHandoffCurrent = $derived(
    data.decisionState?.jobId === data.job.id
    && data.decisionState?.status === data.job.status
    && data.decisionState?.shortlist.version === data.job.selectionDraft?.version
    && recordArray(data.decisionState?.shortlist.staleItems).length === 0
    && (nonNegativeInteger(data.decisionState?.staleCounts.shortlist) ?? 0) === 0
    && recordArray(data.decisionState?.deepResearch.blockers).length === 0,
  );
  const riskChecks = $derived(recordArray(data.decisionState?.challenges).filter((challenge) => (
    referenceIsSelected(objectRecord(challenge)?.idea)
  )).length);
  const staleRiskChecks = $derived(
    nonNegativeInteger(data.decisionState?.staleCounts?.challenges) ?? 0,
  );
  // First-hand evidence the owner saved via "Add your evidence". Non-retracted rows
  // whose idea is still on the current shortlist are already the only ones the state
  // service returns, so the same selectedRefs filter as the checks applies.
  const ownerEvidence = $derived(recordArray(data.decisionState?.ownerEvidence).filter((record) => (
    referenceIsSelected(objectRecord(record)?.idea)
  )).length);
  // The gate carries the same ledger line the guide panel uses, so the state a
  // user assembled across the workspace is restated once before they pay for it.
  // Without the decision-tools grant there are no checks to count.
  const recordLine = $derived(
    decisionTools
      ? guideRecordLine({
        shortlisted: selectedCount,
        checks: riskChecks,
        stale: staleRiskChecks,
        contextSaved: Boolean(data.decisionState?.profile),
        ownerEvidence,
      })
      : `${selectedCount} SHORTLISTED`,
  );
  // Unresolved decision questions surfaced at the commit gate, plus any
  // evidence check whose overall call came back weakened/contradicted.
  const openAssumptions = $derived(recordArray(data.decisionState?.assumptions).filter((assumption) => (
    referenceIsSelected(objectRecord(assumption)?.idea)
    && objectRecord(assumption)?.ownerState === "OPEN"
  )).length);
  const weakenedChecks = $derived(recordArray(data.decisionState?.challenges).filter((challenge) => (
    referenceIsSelected(objectRecord(challenge)?.idea)
    && (objectRecord(challenge)?.overall === "weakened" || objectRecord(challenge)?.overall === "contradicted")
  )).length);
  const solutionNameCounts = $derived((data.solutions ?? []).reduce((counts, solution) => {
    counts.set(solution.solution_name, (counts.get(solution.solution_name) ?? 0) + 1);
    return counts;
  }, new Map<string, number>()));

  type ReceiptRow = { label: string; value: string };

  function objectRecord(value: unknown): Record<string, unknown> | null {
    return value !== null && typeof value === "object" && !Array.isArray(value)
      ? value as Record<string, unknown>
      : null;
  }

  function recordArray(value: unknown): Record<string, unknown>[] {
    return Array.isArray(value)
      ? value.flatMap((candidate) => {
          const record = objectRecord(candidate);
          return record ? [record] : [];
        })
      : [];
  }

  function trimmedString(value: unknown): string | null {
    if (typeof value !== "string") return null;
    return value.trim() || null;
  }

  function referenceKey(reference: unknown): string | null {
    const record = objectRecord(reference);
    const ideaId = trimmedString(record?.ideaId);
    const ideaRevision = record?.ideaRevision;
    return ideaId
      && typeof ideaRevision === "number"
      && Number.isInteger(ideaRevision)
      && ideaRevision >= 1
      ? `${ideaId}:${ideaRevision}`
      : null;
  }

  function referenceIsSelected(reference: unknown): boolean {
    const key = referenceKey(reference);
    return key !== null && selectedRefs.has(key);
  }

  function scopedFounderFitResults(
    founderFit: unknown,
    references: Array<{ ideaId: string; ideaRevision: number }>,
  ): Record<string, unknown>[] | null {
    const receipt = objectRecord(founderFit);
    const analysis = objectRecord(receipt?.analysis);
    if (receipt?.stale !== false || !Array.isArray(analysis?.results)) return null;

    const results = recordArray(analysis.results);
    if (results.length !== references.length) return null;
    const expected = new Set(references.map((reference) => `${reference.ideaId}:${reference.ideaRevision}`));
    const actual = new Set(results.map(referenceKey).filter((key): key is string => key !== null));
    return actual.size === results.length
      && expected.size === actual.size
      && [...expected].every((key) => actual.has(key))
      ? results
      : null;
  }

  function matchesIdea(
    reference: unknown,
    idea: SolutionPreview,
  ): boolean {
    return referenceKey(reference) === `${idea.idea_id}:${idea.idea_revision ?? 1}`;
  }

  function founderFitFor(idea: SolutionPreview) {
    const current = recordArray(data.decisionState?.founderFit?.results).find((result) => (
      matchesIdea(result.idea, idea)
    ));
    const verdict = trimmedString(current?.verdict);
    if (!verdict) return null;

    const detail = fitResults?.find((result) => matchesIdea(result, idea)) ?? null;
    return { verdict, detail };
  }

  function founderFitLabel(verdict: unknown): string | null {
    switch (verdict) {
      case "fits": return "Fits your constraints";
      case "needs_reshape": return "Needs reshape";
      case "blocked": return "Blocked by your constraints";
      case "insufficient_evidence": return "Insufficient evidence";
      default: return null;
    }
  }

  function testOutcome(outcome: unknown): string | null {
    const normalized = trimmedString(outcome)?.toUpperCase();
    switch (normalized) {
      case "PASS": return "Passed";
      case "FAIL": return "Failed";
      case "AMBIGUOUS": return "Ambiguous";
      case "INVALID": return "Invalid";
      default: return null;
    }
  }

  function collaboratorSignal(idea: SolutionPreview): string | null {
    if (data.collaboratorSignalsStatus !== "loaded") return null;

    const id = idea.idea_id;
    const exactCount = id ? nonNegativeInteger(objectRecord(data.solutionVotesById)?.[id]) : null;
    const legacySafe = solutionNameCounts.get(idea.solution_name) === 1;
    const legacyCount = legacySafe
      ? nonNegativeInteger(objectRecord(data.solutionVotes)?.[idea.solution_name])
      : null;
    const count = exactCount ?? legacyCount ?? 0;
    const latestNoteRecord = recordArray(data.voteRationales).find((vote) => (
      id && trimmedString(vote.solutionId)
        ? trimmedString(vote.solutionId) === id
        : !trimmedString(vote.solutionId)
          && legacySafe
          && trimmedString(vote.solutionName) === idea.solution_name
    ));
    const latestNote = trimmedString(latestNoteRecord?.comment);

    if (count <= 0 && !latestNote) return null;
    const countText = count > 0
      ? `${count} collaborator ${count === 1 ? "vote" : "votes"}`
      : "Collaborator note";
    return latestNote ? `${countText}. Latest note: “${latestNote}”` : countText;
  }

  function receiptRows(idea: SolutionPreview): ReceiptRow[] {
    const rows: ReceiptRow[] = [];
    // red_team_verdict currently has no durable per-idea code-owned provenance marker.
    // Because generator output can populate the same BaseSolutionIdea field, a naked value
    // is not safe receipt evidence. Keep it omitted until the producer resets then stamps it.

    const fit = founderFitFor(idea);
    const fitLabel = fit ? founderFitLabel(fit.verdict) : null;
    if (fitLabel) {
      rows.push({
        label: "Founder fit",
        value: trimmedString(fit?.detail?.summary)
          ? `${fitLabel}: ${trimmedString(fit?.detail?.summary)}`
          : fitLabel,
      });
    }

    const impactRank: Record<string, number> = { DECISIVE: 3, HIGH: 2, MEDIUM: 1 };
    const openAssumption = recordArray(data.decisionState?.assumptions)
      .filter((assumption) => (
        matchesIdea(assumption.idea, idea) && assumption.ownerState === "OPEN"
      ))
      .sort((left, right) => (
        (impactRank[trimmedString(right.impact) ?? ""] ?? 0)
        - (impactRank[trimmedString(left.impact) ?? ""] ?? 0)
      ))[0];
    const unresolved = trimmedString(fit?.detail?.blockingConflict)
      || trimmedString(openAssumption?.statement)
      || trimmedString(fit?.detail?.decisionChangingUnknown);
    if (unresolved) rows.push({ label: "Open question", value: unresolved });

    const conclusion = recordArray(data.decisionState?.conclusions).find((candidate) => (
      matchesIdea(candidate.idea, idea)
    ));
    const outcome = conclusion ? testOutcome(conclusion.outcome) : null;
    if (outcome) rows.push({ label: "Latest test", value: outcome });

    const collaborator = collaboratorSignal(idea);
    if (collaborator) rows.push({ label: "Collaborator signal", value: collaborator });
    return rows;
  }
  const creditBalance = $derived(
    data.billingLoadState?.balanceUnavailable
      ? null
      : nonNegativeInteger(data.creditBalance),
  );
  const researchCost = $derived(
    data.billingLoadState?.costsUnavailable
      ? null
      : nonNegativeInteger(data.stageCosts.deep_research),
  );
  const selectionFingerprint = $derived(data.decisionState?.shortlist.fingerprint ?? null);
  const creditDataValid = $derived(creditBalance !== null && researchCost !== null);
  const creditAvailabilityMessage = $derived(
    data.billingLoadState?.balanceUnavailable && data.billingLoadState?.costsUnavailable
      ? "Your credit balance and the current Deep Research price could not be loaded."
      : data.billingLoadState?.balanceUnavailable
        ? "Your credit balance could not be loaded."
        : data.billingLoadState?.costsUnavailable
          ? "The current Deep Research price could not be loaded."
          : "Credit information is invalid or unavailable.",
  );
  const hasEnoughCredits = $derived(
    creditBalance !== null
    && researchCost !== null
    && creditBalance >= researchCost,
  );
  const postChargeBalance = $derived(
    creditBalance !== null && researchCost !== null
      ? creditBalance - researchCost
      : null,
  );
  // ── "Check my idea" (validate_idea): subject-switch acknowledgement ──
  // Deep Research on a validate run is expected to continue with THE USER'S idea. A
  // scope that omits it means the user is consciously switching subjects — that gets an
  // explicit acknowledgement at the money moment (mixed scope needs none, and a run whose
  // seed isn't purchasable gets the neutral wording).
  const isValidation = $derived(data.job.entryMode === "validate_idea");
  const validationSeeds = $derived(
    isValidation
      ? data.solutions.filter(
          (s) => s.source_frame === "user_seed" && s.generation_operation_id === "validate",
        )
      : [],
  );
  const validationSeedAmbiguous = $derived(validationSeeds.length > 1);
  const validationSeed = $derived(validationSeeds.length === 1 ? validationSeeds[0] : null);
  const selectedValidationSeeds = $derived(
    selectedIdeas.filter(
      (s) => s.source_frame === "user_seed" && s.generation_operation_id === "validate",
    ),
  );
  const scopeIncludesSeed = $derived(
    Boolean(validationSeed?.idea_id)
    && selectedValidationSeeds.some(
      (selected) => selected.idea_id === validationSeed?.idea_id
        && (selected.idea_revision ?? 1) === (validationSeed?.idea_revision ?? 1),
    ),
  );
  const validationSubjectSwitch = $derived(
    isValidation && selectedCount > 0 && !scopeIncludesSeed,
  );
  let subjectSwitchAcknowledged = $state(false);
  $effect(() => {
    // Any scope change resets the acknowledgement.
    void selectedRefs;
    subjectSwitchAcknowledged = false;
  });

  const canStart = $derived(
    currentStatus === "AWAITING_SELECTION"
    && canMutate
    && selectedCount > 0
    && !data.selectionLoadState.solutionsUnavailable
    && data.selectionLoadState.invalidSolutionCount === 0
    && data.workspace.scopeSource !== "preview"
    && data.workspace.scopeSource !== "blocked"
    && scopeMatchesSaved
    && decisionHandoffCurrent
    && Boolean(data.decisionState?.deepResearch.eligible)
    && Boolean(selectionFingerprint)
    && creditDataValid
    && hasEnoughCredits
    && (!confirmationMismatch || mismatchAcknowledged)
    && !validationSeedAmbiguous
    && (!validationSubjectSwitch || subjectSwitchAcknowledged)
    && !submitting,
  );

  function routeHref(slug: "compare" | "risks"): string {
    return `/jobs/${data.job.id}/selection/${slug}${data.workspace.canonicalQuery}`;
  }

  function apiErrorCode(error: ApiError): string | undefined {
    if (!error.details || typeof error.details !== "object") return undefined;
    const code = (error.details as Record<string, unknown>).code;
    return typeof code === "string" ? code : undefined;
  }

  async function startResearch(): Promise<void> {
    if (!canStart) return;
    submitting = true;
    submitError = "";
    try {
      await selectSolution(data.job.id, {
        clientRequestId,
        expectedDraftVersion: data.decisionState?.shortlist.version ?? 0,
        expectedSelectionFingerprint: selectionFingerprint as string,
        expectedCost: researchCost as number,
        rationale: rationale.trim() || undefined,
      });
      try {
        sessionStorage.removeItem(rationaleStorageKey);
      } catch {
        // Non-fatal: the draft simply outlives the successful start.
      }
      await goto(`/jobs/${data.job.id}`);
    } catch (error) {
      if (error instanceof ApiError && error.status === 402) {
        submitError = researchCost === null
          ? "Credit information changed while you were confirming. Reload this review before trying again."
          : `You need ${researchCost} credits to start this research. Your balance may have changed; add credits, then return to confirm.`;
      } else if (
        error instanceof ApiError
        && error.status === 409
        && [
          "DEEP_RESEARCH_SCOPE_CHANGED",
          "DEEP_RESEARCH_COST_CHANGED",
          "DEEP_RESEARCH_CONFIRMATION_STALE",
          "PRICE_CHANGED",
          "STALE_SELECTION_DRAFT",
          "STALE_SOLUTION_REVISION",
          "AMBIGUOUS_PHASE2_SELECTION",
        ].includes(apiErrorCode(error) ?? "")
      ) {
        const code = apiErrorCode(error);
        confirmationMismatch = {
          previousIdeas: selectedIdeas.map(solutionDisplayTitle),
          previousCost: researchCost,
          kind: [
            "DEEP_RESEARCH_SCOPE_CHANGED",
            "STALE_SELECTION_DRAFT",
            "STALE_SOLUTION_REVISION",
            "AMBIGUOUS_PHASE2_SELECTION",
          ].includes(code ?? "")
            ? "scope"
            : ["DEEP_RESEARCH_COST_CHANGED", "PRICE_CHANGED"].includes(code ?? "")
              ? "cost"
              : "scope_and_cost",
        };
        mismatchAcknowledged = false;
        submitError = "";
        await invalidateAll();
        queueMicrotask(() => mismatchHeading?.focus());
      } else if (
        error instanceof ApiError
        && error.status === 409
        && [
          "DEEP_RESEARCH_ALREADY_STARTED",
          "DEEP_RESEARCH_START_CONFLICT",
          "DEEP_RESEARCH_NOT_AWAITING_SELECTION",
        ].includes(apiErrorCode(error) ?? "")
      ) {
        submitError = "Deep Research was already started from another tab. Opening its live progress now.";
        await invalidateAll();
        await goto(`/jobs/${data.job.id}`, { invalidateAll: true });
      } else {
        submitError = error instanceof Error
          ? error.message
          : "We could not start Deep Research. Your shortlist is still saved.";
      }
    } finally {
      submitting = false;
    }
  }
</script>

<section class="selection-page review-page">
  <header class="selection-page__header">
    <div>
      <h2>Review your shortlist</h2>
      <p class="selection-page__lead">
        {canMutate
          ? "Confirm this exact shortlist before Deep Research begins."
          : "View-only record of the exact shortlist. Open any idea for details; changes and a new research start are unavailable."}
      </p>
    </div>
    {#if selectedCount > 0}
      <p class="review-record">{recordLine}</p>
    {/if}
  </header>

  {#if data.collaboratorSignalsStatus === "unavailable"}
    <p class="collaborator-load-warning" role="status">
      Collaborator feedback is temporarily unavailable. Saved votes or notes may be missing from this page.
    </p>
  {/if}

  {#if selectedCount === 0}
    <div class="selection-page__panel">
      <EmptyState
        title={canMutate ? "Select at least one idea first" : "No saved shortlist to review"}
        description={canMutate
          ? "Return to the comparison, choose up to three ideas, then review the scope again."
          : "This run does not contain a saved shortlist record."}
      >
        <Button
          href={canMutate ? routeHref("compare") : `/jobs/${data.job.id}`}
          label={canMutate ? TOOL_NAMES.compare : "View run"}
        />
      </EmptyState>
    </div>
  {:else}
    <div class="review-grid">
      <div class="review-main">
      <section class="scope-card selection-page__panel" aria-labelledby="selected-ideas-title">
        <div class="scope-card-head">
          <div>
            <p class="review-kicker">Shortlist</p>
            <h3 id="selected-ideas-title">{selectedCount} selected · max 3</h3>
          </div>
          {#if canMutate}
            <a href={rankedIdeasHref(data.job.id)}>{CHOOSE_IDEAS_LABEL}</a>
          {:else}
            <span class="readonly-label">Saved scope</span>
          {/if}
        </div>
        <ol class="selected-list">
          {#each selectedIdeas as idea, index (`${idea.idea_id}:${idea.idea_revision ?? 1}`)}
            {@const composite = displayCompositeScore(idea)}
            {@const receipt = receiptRows(idea)}
            <li>
              <button type="button" class="idea-row" onclick={() => (detailIndex = index)}>
                <span class="idea-ordinal" aria-hidden="true">{index + 1}</span>
                <span class="idea-body">
                  <strong>
                    {solutionDisplayTitle(idea)}
                    {#if isValidation && idea.source_frame === "user_seed" && idea.generation_operation_id === "validate"}
                      <span class="score-chip">Your idea</span>
                    {/if}
                  </strong>
                  <span class="idea-summary">{idea.short_description ?? idea.description}</span>
                  {#if composite !== null || idea.idea_tier === "bundle"}
                    <span class="idea-meta-row">
                      {#if composite !== null}
                        <span class="score-chip">Research score {Math.round(composite * 100)}</span>
                      {/if}
                      {#if idea.idea_tier === "bundle"}
                        <span class="tier-chip">
                          Bundle{#if (idea.pain_points_addressed?.length ?? 0) > 0}&nbsp;· {idea.pain_points_addressed?.length} pain signals{/if}
                        </span>
                      {/if}
                    </span>
                  {/if}
                </span>
                {#if (idea.idea_revision ?? 1) > 1}<small>Updated version</small>{/if}
              </button>
              {#if receipt.length > 0}
                <dl class="idea-receipt" aria-label={`Decision receipt for ${solutionDisplayTitle(idea)}`}>
                  {#each receipt as row (row.label)}
                    <div>
                      <dt>{row.label}</dt>
                      <dd>{row.value}</dd>
                    </div>
                  {/each}
                </dl>
              {/if}
            </li>
          {/each}
        </ol>
        <p class="scope-terms">
          Starting Deep Research locks this exact shortlist. Ideas cannot change during the run, and any active discovery share closes once the run is successfully queued.
        </p>
        <!-- Advertising a tool this owner cannot open: the link 307-bounces to
             /selection/compare, so the whole summary is gated with it. -->
        {#if decisionTools}
        <div class="risk-summary" data-tour="risk-summary">
          <div class="risk-summary__head">
            <div>
              <strong>Risk check</strong>
              <Badge variant="muted" size="sm">Optional</Badge>
            </div>
            <a href={routeHref("risks")}>
              {canMutate
                ? riskChecks > 0 ? "Review checks" : STRESS_TEST_EVIDENCE_LABEL
                : "Open evidence record"}
            </a>
          </div>
          <!-- One sentence, never two that appear to contradict: with nothing
               current AND older checks archived, the old copy read "No risk check
               saved" directly above "Older checks were archived". -->
          <p>
            {#if riskChecks > 0}
              {riskChecks} current evidence {riskChecks === 1 ? "check is" : "checks are"} saved. This does not change your selected ideas.
            {:else if staleRiskChecks > 0}
              No current risk check: earlier checks were archived when their source evidence changed.{canMutate ? " You can continue because this step is optional." : ""}
            {:else}
              {canMutate
                ? "No risk check saved. You can continue because this step is optional."
                : "No risk check was saved before selection closed."}
            {/if}
          </p>
          {#if ownerEvidence > 0}
            <!-- Owner evidence was previously invisible here even though it is already
                 in play: buildSelectionChallengeEvidence() folds it into every risk-check
                 pack and the chat analyst cites it as O1/O2. It is NOT part of the Deep
                 Research payload, so the copy must not promise that. -->
            <p>
              <a href={routeHref("risks")}>{ownerEvidence} {ownerEvidence === 1 ? "piece" : "pieces"} of your own evidence</a>
              {ownerEvidence === 1 ? "is" : "are"} saved against these ideas. Risk checks and the analyst cite it.
            </p>
          {/if}
          {#if openAssumptions > 0}
            <p>
              <a href={routeHref("risks")}>{openAssumptions} open {openAssumptions === 1 ? "question" : "questions"} to resolve</a>
              {openAssumptions === 1 ? "is" : "are"} tracked but not yet answered. They do not block research.
            </p>
          {/if}
          {#if weakenedChecks > 0}
            <p class="risk-flag">
              {weakenedChecks} {weakenedChecks === 1 ? "check" : "checks"} found claims weakened or contradicted{canMutate ? ". Worth a look before you start." : "."}
            </p>
          {/if}
          {#if riskChecks > 0 && staleRiskChecks > 0}
            <!-- Archival is bookkeeping, not a risk signal: muted, not warning-tinted. -->
            <p class="archived-note">Older checks were archived when their source evidence changed. They do not block research.</p>
          {/if}
        </div>
        {/if}
      </section>

      <!-- Value case and the optional note live in the left column: the right rail
           is the transactional path, and a rail taller than the viewport cannot
           actually stick, which put the commit button permanently below the fold. -->
      <section class="value-card selection-page__panel" aria-labelledby="deliverables-title">
        <p class="review-kicker">Deep Research report</p>
        <h3 id="deliverables-title">What you get</h3>
        <p class="delivery-readiness">Typically ready within the hour. It runs in the background, so you can leave and come back.</p>
        <ul class="deliverables">
          <li>Demand &amp; pain evidence: validated pain points with source quotes</li>
          <li>Competitor &amp; alternatives landscape</li>
          <li>SEO &amp; keyword strategy</li>
          <li>Go-to-market playbook &amp; monetization</li>
          <li>Risks, a clear recommendation, and decision-changing conditions</li>
        </ul>
        <p class="refund-note">Run protection: if the run fails or finds too little data, credits return automatically.</p>
        <!-- /sample-report lives in the (public) route group, so following it in
             this tab drops the user out of the app shell mid-commit. -->
        {#if data.sampleReportAvailable}
          <a class="deliverables__sample" href="/sample-report" target="_blank" rel="noopener">
            See a sample report →<span class="sr-only"> (opens in a new tab)</span>
          </a>
        {:else}
          <p class="deliverables__sample-unavailable">Sample report temporarily unavailable.</p>
        {/if}
      </section>

      <section class="note-card selection-page__panel">
        {#if canMutate}
          <FormField
            id="research-rationale"
            kind="textarea"
            label="Why these ideas?"
            optional
            hint="Private to your workspace. Keep the reasoning behind this choice for your future self and the Analyst."
            bind:value={rationale}
            maxlength={2000}
            rows={4}
            placeholder="Add a note for your future self about this choice."
          />
        {:else}
          <p class="review-kicker">Selection note</p>
          <h3>Why these ideas?</h3>
          <p class:empty-note={!rationale.trim()}>
            {rationale.trim() || "No note was saved with this selection."}
          </p>
        {/if}
      </section>
      </div>

      <aside class="confirm-card" aria-labelledby="confirm-title">
        <h3 id="confirm-title">{selectedCount} {selectedCount === 1 ? "idea" : "ideas"}, one research run</h3>
        <div class="commit-record-wrap" role="group" aria-label="Credit summary">
          <!-- One priced surface. chargeForStageInTx(..., 'deep_research') charges once
               per run, so this record must never imply per-idea multiplication. -->
          <p class="commit-record" data-tour="flat-price">
            <span>FLAT PRICE <b>{researchCost === null ? "UNAVAILABLE" : `${researchCost}\u00a0CREDITS`}</b></span>
            <i aria-hidden="true">·</i>
            <span>COVERS <b>1-3 IDEAS</b></span>
            <i aria-hidden="true">·</i>
            <span>BALANCE AFTER <b>{postChargeBalance ?? "UNAVAILABLE"}</b></span>
          </p>
        </div>

        {#if confirmationMismatch}
          <section class="confirmation-change" aria-labelledby="confirmation-change-title">
            <h4 id="confirmation-change-title" tabindex="-1" bind:this={mismatchHeading}>
              Review the updated confirmation
            </h4>
            <p>
              {confirmationMismatch.kind === "scope"
                ? "Your saved shortlist changed before the run started."
                : confirmationMismatch.kind === "cost"
                  ? "The Deep Research price changed before the run started."
                  : "Your saved shortlist or price changed before the run started."}
              Nothing was charged or started.
            </p>
            <dl>
              <div>
                <dt>Previously reviewed</dt>
                <dd>{confirmationMismatch.previousIdeas.join(" · ") || "No ideas"} · {confirmationMismatch.previousCost ?? "unknown"} credits</dd>
              </div>
              <div>
                <dt>Current confirmation</dt>
                <dd>{selectedIdeas.map(solutionDisplayTitle).join(" · ") || "No ideas"} · {researchCost ?? "unknown"} credits</dd>
              </div>
            </dl>
            {#if !mismatchAcknowledged}
              <button
                type="button"
                class="credit-link credit-link--button"
                onclick={() => {
                  mismatchAcknowledged = true;
                  clientRequestId = crypto.randomUUID();
                }}
              >Use this updated scope and price</button>
            {/if}
          </section>
        {/if}

        {#if validationSeedAmbiguous}
          <section class="confirmation-change" aria-labelledby="subject-identity-title">
            <h4 id="subject-identity-title">Your submitted idea cannot be identified safely</h4>
            <p>
              More than one current candidate is marked as your submitted idea. Reload the
              shortlist before starting Deep Research.
            </p>
          </section>
        {:else if validationSubjectSwitch}
          <section class="confirmation-change" aria-labelledby="subject-switch-title">
            <h4 id="subject-switch-title">You're researching a different idea</h4>
            <p>
              {#if validationSeed}
                Deep Research will cover {selectedIdeas.map(solutionDisplayTitle).join(" · ")}
                instead of your idea, {solutionDisplayTitle(validationSeed)}. Your idea's
                check stays saved on this run. You can start it later.
              {:else}
                Your submitted idea isn't available for research on this run, so Deep
                Research will cover {selectedIdeas.map(solutionDisplayTitle).join(" · ")}.
                Your idea's check stays saved.
              {/if}
            </p>
            {#if !subjectSwitchAcknowledged}
              <button
                type="button"
                class="credit-link credit-link--button"
                onclick={() => { subjectSwitchAcknowledged = true; }}
              >Yes, research {selectedIdeas.length === 1 ? solutionDisplayTitle(selectedIdeas[0]) : "these ideas"}</button>
            {/if}
          </section>
        {/if}

        {#if !creditDataValid}
          <p class="credit-warning">{creditAvailabilityMessage} Reload before starting so you can confirm the exact charge.</p>
          <button class="credit-link credit-link--button" type="button" onclick={() => void invalidateAll()}>Reload credit information</button>
        {/if}

        {#if data.workspace.scopeSource === "preview"}
          <p class="credit-warning">
            {canMutate
              ? "Save at least one idea in Compare before starting research."
              : "No saved idea scope is available in this selection record."}
          </p>
          {#if canMutate}<a class="credit-link" href={rankedIdeasHref(data.job.id)}>Choose ideas</a>{/if}
        {:else if !scopeMatchesSaved}
          <p class="credit-warning">
            {canMutate
              ? "This linked scope does not match your saved shortlist yet."
              : "This link does not match the shortlist saved for this run."}
          </p>
          {#if canMutate}<a class="credit-link" href={routeHref("compare")}>Review and save this scope</a>{/if}
        {/if}

        <!-- Advisory, so it sits outside the credit-warning blockers and leaves the
             button enabled: two framings of one product is a defensible purchase,
             just not one to make unknowingly. -->
        {#each overlapWarnings as overlap (overlap.sharedProduct)}
          <p class="overlap-warning">
            {overlapWarningText(overlap)}
            {#if canMutate}<a class="credit-link" href={rankedIdeasHref(data.job.id)}>Change your shortlist</a>{/if}
          </p>
        {/each}

        {#if submitError}<p class="submit-error" role="alert">{submitError}</p>{/if}
        <SubmitButton
          type="button"
          label={confirmationMismatch && mismatchAcknowledged
            ? "Confirm updated scope"
            : "Start Deep Research"}
          loadingText="Starting research…"
          loading={submitting}
          disabled={!canStart}
          describedBy={!canStart && !submitting ? "start-research-status" : undefined}
          onclick={() => void startResearch()}
        />
        {#if !canStart && !submitting}
          <p id="start-research-status" class="sr-only">
            {selectedCount === 0
              ? "Select at least one idea before starting research."
              : data.workspace.scopeSource === "preview"
                ? "Save at least one idea before starting research."
                : !scopeMatchesSaved
                  ? "Save this exact research scope before starting research."
                : !creditDataValid
                  ? "Reload valid credit information before starting research."
                  : !selectionFingerprint
                    ? "Reload the exact shortlist confirmation before starting research."
                  : confirmationMismatch && !mismatchAcknowledged
                    ? "Review and accept the updated shortlist and price before starting research."
                : !hasEnoughCredits
                  ? "Top up your balance before starting research."
                  : "Deep Research cannot be started in the current job state."}
          </p>
        {/if}
      </aside>
    </div>

    <!-- Read-only inspection at the gate: same overlay the ranked list and the
         post-commit summary use, so an idea looks the same wherever it is opened.
         No onSelect — the shortlist is edited in Compare, not here. -->
    {#if detailIndex !== null && selectedIdeas[detailIndex]}
      <SolutionDetail
        open
        solution={selectedIdeas[detailIndex]}
        solutions={selectedIdeas}
        currentIndex={detailIndex}
        jobId={data.job.id}
        lifecycle="reference"
        onNavigate={(index) => (detailIndex = index)}
        onClose={() => (detailIndex = null)}
      />
    {/if}
  {/if}
</section>

<style>
  .review-grid { display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(21rem, 0.75fr); gap: var(--space-6); align-items: start; }
  .review-main { display: grid; min-width: 0; gap: var(--space-6); }
  .review-record { margin: 0; color: var(--color-text-muted); font: 700 var(--text-xs)/var(--leading-tight) var(--font-mono); letter-spacing: var(--tracking-wider); white-space: nowrap; }
  .collaborator-load-warning { margin: 0; color: var(--color-warning-text); font-size: var(--text-13); font-weight: 600; line-height: var(--leading-snug); }
  .scope-card { min-width: 0; overflow: hidden; overflow-wrap: anywhere; }
  .scope-card-head { display: flex; justify-content: space-between; gap: var(--space-4); align-items: end; padding: var(--space-5); border-bottom: 1px solid var(--color-border); }
  .review-kicker { margin: 0; color: var(--color-text-muted); font: 700 var(--text-xs)/var(--leading-tight) var(--font-mono); letter-spacing: var(--tracking-wider); text-transform: uppercase; }
  .note-card h3 { margin: var(--space-2) 0 0; font-family: var(--font-display); font-size: var(--text-lg); line-height: var(--leading-tight); }
  .note-card > p:last-child { margin: var(--space-3) 0 0; color: var(--color-text-secondary); font-size: var(--text-sm); line-height: var(--leading-normal); white-space: pre-wrap; }
  .note-card > p.empty-note { color: var(--color-text-muted); }
  .scope-card h3, .value-card h3, .confirm-card h3 { margin: var(--space-2) 0 0; font-family: var(--font-display); font-size: var(--text-xl); line-height: var(--leading-tight); letter-spacing: var(--tracking-tight); text-wrap: balance; }
  .scope-card-head a, .risk-summary a { color: var(--color-accent-dark); font-size: var(--text-base); font-weight: 700; text-decoration: none; white-space: nowrap; }
  .readonly-label { color: var(--color-text-muted); font-size: var(--text-sm); font-weight: 700; white-space: nowrap; }
  .scope-card-head a:hover, .risk-summary a:hover { text-decoration: underline; text-underline-offset: var(--space-1); }
  .scope-card-head a:focus-visible, .risk-summary a:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  .selected-list { margin: 0; padding: 0; list-style: none; }
  .selected-list li { border-bottom: 1px solid var(--color-border); }
  /* The row is the affordance: inspecting a shortlisted idea opens the same
     detail overlay used by the ranked list, so nobody has to leave the gate to
     see what they are about to pay to research. */
  .idea-row { display: grid; grid-template-columns: var(--space-6) minmax(0, 1fr) auto; gap: var(--space-3); align-items: start; width: 100%; padding: var(--space-4) var(--space-5); border: 0; background: none; font: inherit; color: inherit; text-align: left; cursor: pointer; transition: background var(--duration-fast) var(--ease-default); }
  .idea-row:hover { background: var(--color-bg-surface); }
  .idea-row:focus-visible { outline: 2px solid var(--color-accent); outline-offset: -2px; }
  .idea-body { min-width: 0; }
  .idea-ordinal { display: grid; width: var(--space-6); height: var(--space-6); place-items: center; border-radius: var(--radius-full); color: var(--color-accent-dark); background: var(--color-accent-subtle); font: 700 var(--text-xs)/var(--leading-none) var(--font-mono); }
  .selected-list strong { display: block; font-family: var(--font-display); font-size: var(--text-lg); line-height: var(--leading-snug); letter-spacing: var(--tracking-tight); text-wrap: pretty; }
  .idea-summary { display: -webkit-box; overflow: hidden; margin: var(--space-2) 0 0; color: var(--color-text-secondary); font-size: var(--text-base); line-height: var(--leading-normal); -webkit-box-orient: vertical; -webkit-line-clamp: 2; line-clamp: 2; }
  .selected-list small { color: var(--color-text-muted); font: 600 var(--text-xs)/var(--leading-snug) var(--font-mono); white-space: nowrap; }
  .idea-receipt { display: grid; gap: var(--space-2); margin: calc(var(--space-1) * -1) 0 0; padding: 0 var(--space-5) var(--space-4) calc(var(--space-5) + var(--space-6) + var(--space-3)); }
  .idea-receipt > div { display: grid; grid-template-columns: minmax(7rem, 0.3fr) minmax(0, 1fr); gap: var(--space-3); align-items: start; }
  .idea-receipt dt { color: var(--color-text-muted); font-size: var(--text-sm); font-weight: 600; line-height: var(--leading-normal); }
  .idea-receipt dd { margin: 0; color: var(--color-text-secondary); font-size: var(--text-13); line-height: var(--leading-normal); text-wrap: pretty; }
  .scope-terms { margin: 0; padding: var(--space-3) var(--space-5); color: var(--color-text-muted); background: var(--color-bg-surface); font-size: var(--text-13); line-height: var(--leading-normal); }
  .idea-meta-row { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-top: var(--space-2); }
  .score-chip, .tier-chip { display: inline-flex; align-items: center; padding: 0.125rem var(--space-2); border-radius: var(--radius-md); font: 600 var(--text-xs)/var(--leading-snug) var(--font-mono); font-variant-numeric: tabular-nums; white-space: nowrap; }
  .score-chip { color: var(--color-text-secondary); background: var(--color-bg-surface); box-shadow: inset 0 0 0 1px var(--color-border); }
  .tier-chip { color: var(--color-text-muted); background: var(--color-bg-surface); box-shadow: inset 0 0 0 1px var(--color-border); }
  .value-card, .note-card { min-width: 0; padding: var(--space-5); overflow-wrap: anywhere; }
  .delivery-readiness, .refund-note { max-width: 65ch; margin: var(--space-3) 0 0; color: var(--color-text-secondary); font-size: var(--text-13); line-height: var(--leading-normal); }
  .refund-note { color: var(--color-text-muted); }
  .deliverables { display: grid; gap: var(--space-2); margin: var(--space-4) 0 0; padding: 0; list-style: none; }
  .deliverables li { position: relative; padding-left: var(--space-5); color: var(--color-text-secondary); font-size: var(--text-base); line-height: var(--leading-normal); }
  .deliverables li::before { content: "✓"; position: absolute; left: 0; color: var(--color-success-text); font-weight: 700; }
  .deliverables__sample { display: inline-block; margin-top: var(--space-4); color: var(--color-text-secondary); font: 600 var(--text-xs)/var(--leading-snug) var(--font-mono); text-decoration: none; }
  .deliverables__sample-unavailable { margin: var(--space-4) 0 0; color: var(--color-text-muted); font: 500 var(--text-xs)/var(--leading-snug) var(--font-mono); }
  .deliverables__sample:hover { color: var(--color-text-primary); text-decoration: underline; text-underline-offset: var(--space-1); }
  .deliverables__sample:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  .risk-summary { padding: var(--space-4) var(--space-5); background: color-mix(in srgb, var(--color-bg-surface) 76%, var(--color-bg-elevated)); }
  .risk-summary__head { display: flex; justify-content: space-between; gap: var(--space-4); align-items: center; }
  .risk-summary__head > div { display: flex; gap: var(--space-2); align-items: center; }
  .risk-summary p { max-width: 65ch; margin: var(--space-2) 0 0; color: var(--color-text-secondary); font-size: var(--text-13); line-height: var(--leading-normal); }
  /* Warning tint is reserved for a real risk signal; archival is bookkeeping. */
  .risk-summary .risk-flag { color: var(--color-warning-text); }
  .risk-summary .archived-note { color: var(--color-text-muted); }
  /* Shared emphasis-card recipe (finding: one accent tint token + border-accent
     + shadow-sm), matched by the compare page's .fit-action. */
  .confirm-card { position: sticky; top: var(--space-4); min-width: 0; padding: var(--space-6); overflow-wrap: anywhere; border: 1px solid var(--color-border-accent); border-radius: var(--radius-lg); color: var(--color-text-primary); background: var(--color-accent-subtle); box-shadow: var(--shadow-sm); }
  .confirm-card > p:not(.commit-record, .submit-error, .credit-warning, .overlap-warning) { margin: var(--space-3) 0 var(--space-5); color: var(--color-text-secondary); font-size: var(--text-base); line-height: var(--leading-normal); text-wrap: pretty; }
  .commit-record { display: flex; flex-wrap: wrap; gap: var(--space-1) var(--space-2); margin: 0 0 var(--space-5); color: var(--color-text-muted); font-family: var(--font-mono); font-size: var(--text-xs); font-weight: 700; letter-spacing: 0.07em; line-height: var(--leading-tight); text-transform: uppercase; font-variant-numeric: tabular-nums; font-feature-settings: "zero" 0; }
  .commit-record span, .commit-record b { white-space: nowrap; }
  .commit-record b { color: var(--color-text-primary); font: inherit; }
  .commit-record i { font-style: normal; }
  .confirmation-change {
    display: grid;
    gap: var(--space-3);
    margin-bottom: var(--space-4);
    padding: var(--space-4);
    border: 1px solid var(--color-border-emphasis);
    border-radius: var(--radius-md);
    background: var(--color-bg-elevated);
  }
  .confirmation-change h4 { margin: 0; color: var(--color-text-primary); font-size: var(--text-base); }
  .confirmation-change h4:focus { outline: none; }
  .confirmation-change h4:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  .confirmation-change p { margin: 0; color: var(--color-text-secondary); font-size: var(--text-13); line-height: var(--leading-snug); }
  .confirmation-change dl { display: grid; gap: var(--space-2); margin: 0; }
  .confirmation-change dl > div { display: grid; gap: var(--space-1); }
  .confirmation-change dt { color: var(--color-text-muted); font: 700 var(--text-xs)/var(--leading-tight) var(--font-mono); text-transform: uppercase; }
  .confirmation-change dd { margin: 0; color: var(--color-text-primary); font-size: var(--text-13); overflow-wrap: anywhere; }
  .credit-warning { margin: 0 0 var(--space-1-5); color: var(--color-warning-text); font-size: var(--text-13); font-weight: 600; line-height: var(--leading-snug); }
  /* Plain bordered card, per §9.1 "no accent stripes on ANY edge of cards, zones,
     callouts — callout = plain bordered card or run-in text". Deliberately NOT
     warning-orange: --color-warning-text is byte-identical to --color-accent-dark
     (#9A3412), and this sits inside .confirm-card's accent-subtle fill, so orange text
     here reads as brand chrome rather than a caution. The elevated fill lifts it off
     that background instead. */
  .overlap-warning { margin: 0 0 var(--space-3); padding: var(--space-2) var(--space-3); border: 1px solid var(--color-border-emphasis); border-radius: var(--radius-md); color: var(--color-text-primary); background: var(--color-bg-elevated); font-size: var(--text-13); line-height: var(--leading-snug); }
  .overlap-warning .credit-link { display: block; margin-bottom: 0; margin-top: var(--space-1); }
  .credit-link { display: inline-block; margin-bottom: var(--space-3); color: var(--color-accent-dark); font-size: var(--text-13); font-weight: 700; text-underline-offset: var(--space-1); }
  .credit-link--button { padding: 0; border: 0; background: transparent; font-family: inherit; text-decoration: underline; cursor: pointer; }
  .credit-link:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  .submit-error { margin: 0 0 var(--space-3); padding: var(--space-2); border-radius: var(--radius-sm); color: var(--color-error-text); background: var(--color-error-subtle); font-size: var(--text-13); line-height: var(--leading-snug); }
  @media (max-width: 960px) { .review-grid { grid-template-columns: 1fr; } .confirm-card { position: static; } }
  /* The header collapses to a block below 767px (workspace layout), so the record
     line stops being the flex counterweight and needs its own top gap. */
  @media (max-width: 767px) { .review-record { margin-top: var(--space-3); white-space: normal; } }
  @media (max-width: 560px) {
    .scope-card-head { align-items: flex-start; flex-direction: column; }
    .idea-row { grid-template-columns: var(--space-6) minmax(0, 1fr); padding-inline: var(--space-4); }
    .selected-list small { grid-column: 2; }
    .idea-receipt { padding-inline: calc(var(--space-4) + var(--space-6) + var(--space-3)) var(--space-4); }
    .idea-receipt > div { grid-template-columns: 1fr; gap: var(--space-1); }
    .scope-terms { padding-inline: var(--space-4); }
    .value-card, .note-card { padding: var(--space-4); }
    .risk-summary { padding-inline: var(--space-4); }
    .risk-summary__head { align-items: flex-start; flex-direction: column; gap: var(--space-2); }
    .confirm-card { padding: var(--space-4); }
  }
</style>
