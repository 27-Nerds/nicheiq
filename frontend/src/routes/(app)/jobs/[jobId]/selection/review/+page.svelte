<script lang="ts">
  import { goto, invalidateAll } from "$app/navigation";
  import { getContext } from "svelte";
  import type { PageData } from "./$types";
  import { ApiError, selectSolution } from "$lib/api";
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
    startDeepResearchLabel,
    guideRecordLine,
    CHOOSE_IDEAS_LABEL,
    TOOL_NAMES,
    STRESS_TEST_EVIDENCE_LABEL,
  } from "$lib/selection/labels";

  let { data }: { data: PageData } = $props();

  /** Admin-granted optional decision tools; the risk-check summary is one of them.
   *  /selection/review itself is never gated — only this block inside it. */
  const decisionTools = $derived(data.decisionTools === true);

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
  let rationale = $state(restoreRationale());
  let submitting = $state(false);
  let submitError = $state("");
  /** Index into the shortlist of the idea open in the read-only detail overlay.
   *  Inspecting an idea at the gate must not offer a select control — the
   *  shortlist is edited in Compare — so this opens with lifecycle="reference". */
  let detailIndex = $state<number | null>(null);

  $effect(() => {
    const value = rationale;
    try {
      if (value) sessionStorage.setItem(rationaleStorageKey, value);
      else sessionStorage.removeItem(rationaleStorageKey);
    } catch {
      // Storage unavailable (private mode/quota) — the field still works page-locally.
    }
  });

  const lifecycle = getContext<SelectionWorkspaceLifecycle | undefined>(SELECTION_LIFECYCLE_CONTEXT);
  const currentStatus = $derived(lifecycle?.status || data.job.status);
  const canMutate = $derived(lifecycle?.status ? lifecycle.canMutate : currentStatus === "AWAITING_SELECTION");
  const selectedIdeas = $derived(data.workspace.ideas);
  const selectedCount = $derived(selectedIdeas.length);
  const selectedRefs = $derived(new Set(selectedIdeas.map((idea) => `${idea.idea_id}:${idea.idea_revision ?? 1}`)));
  const savedRefs = $derived(new Set((data.decisionState?.shortlist.items ?? []).map((reference) => (
    `${reference.ideaId}:${reference.ideaRevision}`
  ))));
  const scopeMatchesSaved = $derived(
    selectedRefs.size === savedRefs.size && [...selectedRefs].every((reference) => savedRefs.has(reference)),
  );
  const riskChecks = $derived((data.decisionState?.challenges ?? []).filter((challenge) => (
    selectedRefs.has(`${challenge.idea.ideaId}:${challenge.idea.ideaRevision}`)
  )).length);
  const staleRiskChecks = $derived(data.decisionState?.staleCounts.challenges ?? 0);
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
      })
      : `${selectedCount} SHORTLISTED`,
  );
  // Unresolved decision questions surfaced at the commit gate, plus any
  // evidence check whose overall call came back weakened/contradicted.
  const openAssumptions = $derived((data.decisionState?.assumptions ?? []).filter((assumption) => (
    selectedRefs.has(`${assumption.idea.ideaId}:${assumption.idea.ideaRevision}`)
    && assumption.ownerState === "OPEN"
  )).length);
  const weakenedChecks = $derived((data.decisionState?.challenges ?? []).filter((challenge) => (
    selectedRefs.has(`${challenge.idea.ideaId}:${challenge.idea.ideaRevision}`)
    && (challenge.overall === "weakened" || challenge.overall === "contradicted")
  )).length);
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
  const creditShortfall = $derived(
    creditBalance !== null && researchCost !== null && creditBalance < researchCost
      ? researchCost - creditBalance
      : null,
  );
  const canStart = $derived(
    currentStatus === "AWAITING_SELECTION"
    && canMutate
    && selectedCount > 0
    && data.workspace.scopeSource !== "preview"
    && scopeMatchesSaved
    && Boolean(data.decisionState?.deepResearch.eligible)
    && creditDataValid
    && hasEnoughCredits
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
        solutionNames: selectedIdeas.map((idea) => idea.solution_name),
        solutionIds: selectedIdeas.flatMap((idea) => idea.idea_id ? [idea.idea_id] : []),
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
      <p class="selection-page__lead">Nothing is charged until you confirm this exact set of ideas.</p>
    </div>
    {#if selectedCount > 0}
      <p class="review-record">{recordLine}</p>
    {/if}
  </header>

  {#if selectedCount === 0}
    <div class="selection-page__panel">
      <EmptyState
        title="Select at least one idea first"
        description="Return to the comparison, choose up to three ideas, then review the scope again."
      >
        <Button href={routeHref("compare")} label={TOOL_NAMES.compare} />
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
            <!-- Flat pricing verified: one chargeForStageInTx(…,'deep_research') per run
                 (backend/src/routes/jobs.ts), never multiplied by idea count. -->
            <p class="flat-price-note" data-tour="flat-price">
              {researchCost === null
                ? "One price for up to 3 ideas — the cost does not multiply per idea."
                : `One price for up to 3 ideas — the same ${researchCost} credits for 1, 2, or 3.`}
            </p>
          </div>
          <a href={routeHref("compare")}>{CHOOSE_IDEAS_LABEL}</a>
        </div>
        <ol class="selected-list">
          {#each selectedIdeas as idea, index (`${idea.idea_id}:${idea.idea_revision ?? 1}`)}
            {@const composite = displayCompositeScore(idea)}
            <li>
              <button type="button" class="idea-row" onclick={() => (detailIndex = index)}>
                <span class="idea-ordinal" aria-hidden="true">{index + 1}</span>
                <span class="idea-body">
                  <strong>{solutionDisplayTitle(idea)}</strong>
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
            </li>
          {/each}
        </ol>
        <!-- Advertising a tool this owner cannot open: the link 307-bounces to
             /selection/compare, so the whole summary is gated with it. -->
        {#if decisionTools}
        <div class="risk-summary" data-tour="risk-summary">
          <div class="risk-summary__head">
            <div>
              <strong>Risk check</strong>
              <Badge variant="muted" size="sm">Optional</Badge>
            </div>
            <a href={routeHref("risks")}>{riskChecks > 0 ? "Review checks" : STRESS_TEST_EVIDENCE_LABEL}</a>
          </div>
          <!-- One sentence, never two that appear to contradict: with nothing
               current AND older checks archived, the old copy read "No risk check
               saved" directly above "Older checks were archived". -->
          <p>
            {#if riskChecks > 0}
              {riskChecks} current evidence {riskChecks === 1 ? "check is" : "checks are"} saved. This does not change your selected ideas.
            {:else if staleRiskChecks > 0}
              No current risk check: earlier checks were archived when their source evidence changed. You can continue because this step is optional.
            {:else}
              No risk check saved. You can continue because this step is optional.
            {/if}
          </p>
          {#if openAssumptions > 0}
            <p>
              <a href={routeHref("risks")}>{openAssumptions} open {openAssumptions === 1 ? "question" : "questions"} to resolve</a>
              — tracked but not yet answered. They do not block research.
            </p>
          {/if}
          {#if weakenedChecks > 0}
            <p class="risk-flag">
              {weakenedChecks} {weakenedChecks === 1 ? "check" : "checks"} found claims weakened or contradicted — worth a look before you start.
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
        <ul class="deliverables">
          <li>Demand &amp; pain evidence — validated pain points with source quotes</li>
          <li>Competitor &amp; alternatives landscape</li>
          <li>SEO &amp; keyword strategy</li>
          <li>Go-to-market playbook &amp; monetization</li>
          <li>Risks &amp; a clear go / no-go verdict</li>
        </ul>
        <!-- /sample-report lives in the (public) route group, so following it in
             this tab drops the user out of the app shell mid-commit. -->
        <a class="deliverables__sample" href="/sample-report" target="_blank" rel="noopener">
          See a sample report →<span class="sr-only"> (opens in a new tab)</span>
        </a>
      </section>

      <section class="note-card selection-page__panel">
        <FormField
          id="research-rationale"
          kind="textarea"
          label="Why these ideas?"
          optional
          hint="Leave a note so you can remember the reasoning behind this choice."
          bind:value={rationale}
          maxlength={2000}
          rows={4}
          placeholder="Add a note for your future self about this choice."
        />
      </section>
      </div>

      <aside class="confirm-card" aria-labelledby="confirm-title">
        <p class="review-kicker">Confirmation</p>
        <h3 id="confirm-title">{selectedCount} {selectedCount === 1 ? "idea" : "ideas"}, one research run</h3>
        <!-- Duration: no single authoritative pipeline number exists (docs disagree:
             ~35 min dashboard copy vs ~45 min designer brief), so this stays a
             deliberately loose "within the hour" expectation. -->
        <p>Typically ready within the hour — it runs in the background, so you can leave and come back.</p>

        <div class="price-summary" aria-label="Credit summary">
          <div class="price-summary__heading">
            <span>Credit summary</span>
            <strong>{researchCost === null ? "Unavailable" : `${researchCost} credits total`}</strong>
          </div>
          <!-- One unit, stated once in the heading: the rows were previously mixing
               "731", "−100" and "631 credits" in a four-row ledger. -->
          <div><span>Available balance</span><strong>{creditBalance ?? "Unavailable"}</strong></div>
          <div><span>Deep Research cost</span><strong>{researchCost === null ? "Unavailable" : `−${researchCost}`}</strong></div>
          <div class="post-charge">
            <span>Balance after starting</span>
            <strong>{postChargeBalance === null ? "Unavailable" : postChargeBalance}</strong>
          </div>
        </div>
        <ul class="price-notes">
          <li>You are charged only after you start the run.</li>
          <li>Starting locks this shortlist — ideas can’t be changed during the run.</li>
          <!-- Refund truth: failJob() auto-refunds the in-flight stage on failure, and
               INSUFFICIENT_DATA quality stops go through the same path
               (backend/src/services/jobService.ts). -->
          <li>If the run fails or finds too little data, credits are returned automatically.</li>
        </ul>

        {#if !creditDataValid}
          <p class="credit-warning">{creditAvailabilityMessage} Reload before starting so you can confirm the exact charge.</p>
          <button class="credit-link credit-link--button" type="button" onclick={() => void invalidateAll()}>Reload credit information</button>
        {:else if creditShortfall !== null}
          <p class="credit-warning">You need {creditShortfall} more credits before you can start.</p>
          <a class="credit-link" href="/billing">Add credits</a>
        {/if}

        {#if data.workspace.scopeSource === "preview"}
          <p class="credit-warning">Save at least one idea in Compare before starting research.</p>
          <a class="credit-link" href={routeHref("compare")}>Choose ideas</a>
        {:else if !scopeMatchesSaved}
          <p class="credit-warning">This linked scope does not match your saved shortlist yet.</p>
          <a class="credit-link" href={routeHref("compare")}>Review and save this scope</a>
        {/if}

        {#if submitError}<p class="submit-error" role="alert">{submitError}</p>{/if}
        <SubmitButton
          type="button"
          label={researchCost === null ? "Start Deep Research" : startDeepResearchLabel(researchCost)}
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
                : !hasEnoughCredits
                  ? "Add enough credits before starting research."
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
  .scope-card { min-width: 0; overflow: hidden; overflow-wrap: anywhere; }
  .scope-card-head { display: flex; justify-content: space-between; gap: var(--space-4); align-items: end; padding: var(--space-5); border-bottom: 1px solid var(--color-border); }
  .review-kicker { margin: 0; color: var(--color-text-muted); font: 700 var(--text-xs)/var(--leading-tight) var(--font-mono); letter-spacing: var(--tracking-wider); text-transform: uppercase; }
  .scope-card h3, .value-card h3, .confirm-card h3 { margin: var(--space-2) 0 0; font-family: var(--font-display); font-size: var(--text-xl); line-height: var(--leading-tight); letter-spacing: var(--tracking-tight); text-wrap: balance; }
  .scope-card-head a, .risk-summary a { color: var(--color-accent-dark); font-size: var(--text-base); font-weight: 700; text-decoration: none; white-space: nowrap; }
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
  .flat-price-note { margin: var(--space-1) 0 0; color: var(--color-text-muted); font-size: var(--text-13); line-height: var(--leading-snug); }
  .idea-meta-row { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-top: var(--space-2); }
  .score-chip, .tier-chip { display: inline-flex; align-items: center; padding: var(--space-0-5, 0.125rem) var(--space-2); border-radius: var(--radius-full); font: 600 var(--text-xs)/var(--leading-snug) var(--font-mono); font-variant-numeric: tabular-nums; white-space: nowrap; }
  .score-chip { color: var(--color-text-secondary); background: var(--color-bg-surface); box-shadow: inset 0 0 0 1px var(--color-border); }
  .tier-chip { color: var(--color-text-muted); background: var(--color-bg-surface); box-shadow: inset 0 0 0 1px var(--color-border); }
  .value-card, .note-card { min-width: 0; padding: var(--space-5); overflow-wrap: anywhere; }
  .deliverables { display: grid; gap: var(--space-2); margin: var(--space-4) 0 0; padding: 0; list-style: none; }
  .deliverables li { position: relative; padding-left: var(--space-5); color: var(--color-text-secondary); font-size: var(--text-base); line-height: var(--leading-normal); }
  .deliverables li::before { content: "✓"; position: absolute; left: 0; color: var(--color-success-text); font-weight: 700; }
  .deliverables__sample { display: inline-block; margin-top: var(--space-4); color: var(--color-text-secondary); font: 600 var(--text-xs)/var(--leading-snug) var(--font-mono); text-decoration: none; }
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
  .confirm-card .review-kicker { color: var(--color-accent-dark); }
  .confirm-card > p:not(.review-kicker, .submit-error, .credit-warning) { margin: var(--space-3) 0 var(--space-5); color: var(--color-text-secondary); font-size: var(--text-base); line-height: var(--leading-normal); text-wrap: pretty; }
  .price-summary { display: grid; gap: var(--space-2); margin-top: var(--space-4); padding-top: var(--space-4); border-top: 1px solid var(--color-border); }
  .price-summary > div { display: flex; justify-content: space-between; gap: var(--space-4); align-items: baseline; }
  .price-summary span { color: var(--color-text-secondary); font-size: var(--text-13); }
  .price-summary strong { font: 700 var(--text-base)/var(--leading-tight) var(--font-mono); font-variant-numeric: tabular-nums; white-space: nowrap; }
  .price-summary__heading { margin-bottom: var(--space-1); }
  .price-summary__heading span { color: var(--color-text-primary); font-weight: 700; }
  .price-summary__heading strong { color: var(--color-accent-dark); font-family: var(--font-body); }
  .price-summary .post-charge { margin-top: var(--space-1-5); padding-top: var(--space-3); border-top: 1px solid var(--color-border); }
  .price-summary .post-charge span, .price-summary .post-charge strong { color: var(--color-text-primary); }
  .price-notes { display: grid; gap: var(--space-1-5); margin: var(--space-3) 0 var(--space-4); padding: 0; list-style: none; color: var(--color-text-muted); font-size: var(--text-xs); line-height: var(--leading-snug); }
  .credit-warning { margin: 0 0 var(--space-1-5); color: var(--color-warning-text); font-size: var(--text-13); font-weight: 600; line-height: var(--leading-snug); }
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
    .value-card, .note-card { padding: var(--space-4); }
    .risk-summary { padding-inline: var(--space-4); }
    .risk-summary__head { align-items: flex-start; flex-direction: column; gap: var(--space-2); }
    .confirm-card { padding: var(--space-4); }
    .price-summary > div { align-items: flex-start; flex-direction: column; gap: var(--space-1); }
    .price-summary__heading { align-items: baseline !important; flex-direction: row !important; }
  }
</style>
