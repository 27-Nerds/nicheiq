<script lang="ts">
  import { goto, invalidateAll } from "$app/navigation";
  import { getContext } from "svelte";
  import type { PageData } from "./$types";
  import Tooltip from "$lib/components/ui/Tooltip.svelte";
  import SegmentControl from "$lib/components/ui/SegmentControl.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";
  import Button from "$lib/components/ui/Button.svelte";
  import Badge from "$lib/components/ui/Badge.svelte";
  import EmptyState from "$lib/components/ui/EmptyState.svelte";
  import { ChevronDown, HelpCircle } from "lucide-svelte";
  import { runFounderFit } from "$lib/api";
  import {
    COMPARE_VIEW_MARKET_LABEL,
    COMPARE_VIEW_FOUNDER_LABEL,
  } from "$lib/selection/labels";
  import type {
    FounderFitArtifact,
    FounderFitDimension,
    FounderFitReference,
    FounderFitStatus,
    FounderFitVerdict,
  } from "$lib/types/founderFit";
  import {
    displayCompositeScore,
    originalityScore,
    solutionDisplayTitle,
  } from "$lib/utils/solution-utils";
  import { getWorkspaceTools } from "$lib/selection/workspaceTools";
  import { formatBuildConstraints } from "$lib/selection/profileFormat";
  import { founderFitReasoningSources } from "$lib/selection/founderFitLabels";
  import {
    founderFitMatchesScope,
    founderFitResultFor,
  } from "$lib/selection/founderFitScope";
  import { finiteUnitScore } from "$lib/utils/displayGuards";
  import {
    adversarialReviewFinding,
    adversarialReviewSummary,
    isPremiseUnproven,
    PREMISE_UNPROVEN_LABEL,
  } from "$lib/utils/adversarialReview";
  import { buyerFacingIdeaProse } from "$lib/selection/buyerFacingResearchProse";
  import { rankedIdeasHref as rankedIdeasUrl } from "$lib/selection/rankedIdeas";
  import {
    SELECTION_LIFECYCLE_CONTEXT,
    type SelectionWorkspaceLifecycle,
  } from "../selectionWorkspace";

  let { data }: { data: PageData } = $props();

  const tools = getWorkspaceTools();
  const lifecycle = getContext<SelectionWorkspaceLifecycle | undefined>(SELECTION_LIFECYCLE_CONTEXT);
  const currentStatus = $derived(lifecycle?.status || data.job.status);
  const canMutate = $derived(lifecycle?.status ? lifecycle.canMutate : currentStatus === "AWAITING_SELECTION");
  const rankedIdeasHref = $derived(rankedIdeasUrl(data.job.id));
  const poolOperationPending = $derived(
    data.job.activeDispatchKind === "SEED_IDEA"
      ? ["QUEUED", "RUNNING"].includes(currentStatus)
      : data.job.activeDispatchKind === "REGENERATE"
        ? ["QUEUED", "REGENERATING"].includes(currentStatus)
        : false,
  );
  const viewOnly = $derived(!canMutate && !poolOperationPending);

  function viewHref(view: "market" | "founder"): string {
    const params = new URLSearchParams(data.workspace.canonicalQuery.slice(1));
    params.set("view", view);
    return `?${params.toString()}`;
  }

  /** Admin-granted optional decision tools; "Fit for you" is one of them. */
  const decisionTools = $derived(data.decisionTools === true);
  const compareViewOptions = $derived(
    decisionTools
      ? [
        { value: "market", label: COMPARE_VIEW_MARKET_LABEL },
        { value: "founder", label: COMPARE_VIEW_FOUNDER_LABEL },
      ]
      : [{ value: "market", label: COMPARE_VIEW_MARKET_LABEL }],
  );
  /** Without the grant the research-evidence view is the only view, including for a
   *  ?view=founder deep link — the founder half reads founder-fit, which 403s. */
  const compareView = $derived(
    decisionTools ? data.workspace.compareView : "market",
  );
  const LEADER_EXPLANATION =
    "Leads marks the single highest displayed percentage in a row; rounded ties are not marked.";

  function changeCompareView(view: string): void {
    void goto(viewHref(view as "market" | "founder"), {
      replaceState: true,
      noScroll: true,
      keepFocus: true,
    });
  }

  const metricMap = $derived(new Map(
    (data.metricExplanations?.metrics ?? []).map((metric) => [metric.key, metric]),
  ));

  const scopeReferences = $derived(data.workspace.refs);
  const scopeKey = $derived(
    scopeReferences.map((reference) => `${reference.ideaId}:${reference.ideaRevision}`).join("|"),
  );
  const scopedServerFit = $derived.by(() => {
    const artifact = data.founderFit?.analysis;
    return founderFitMatchesScope(artifact, scopeReferences) ? artifact : null;
  });

  let fitOverride = $state<FounderFitArtifact | null>(null);
  let fitRunning = $state(false);
  let fitError = $state("");
  let fitNotice = $state("");
  let openFitDetails = $state<Record<string, boolean>>({});
  // Plain write-only dedupe guard: making this reactive would retrigger the
  // effect when it synchronizes a newly loaded server artifact.
  let synchronizedFitScope = "";

  $effect(() => {
    const synchronizationKey = `${scopeKey}:${scopedServerFit?.inputFingerprint ?? "none"}`;
    if (synchronizedFitScope === synchronizationKey) return;
    synchronizedFitScope = synchronizationKey;
    fitOverride = null;
    fitError = "";
    fitNotice = "";
  });

  const fitArtifact = $derived(
    founderFitMatchesScope(fitOverride, scopeReferences) ? fitOverride : scopedServerFit,
  );
  const fitIsOutdated = $derived(
    !fitArtifact && Boolean(data.founderFit?.stale || data.founderFit?.analysis),
  );
  const hasExactScope = $derived(
    scopeReferences.length === data.workspace.ideas.length
    && scopeReferences.length > 0,
  );
  const exactScopeError = $derived(
    data.decisionState?.profile && !hasExactScope
      ? "These ideas are missing stable revision references. Reload the shortlist before analyzing fit."
      : "",
  );

  const fitButtonLabel = $derived(
    !data.decisionState?.profile
      ? "Add build limits"
      : fitArtifact
        ? "Refresh analysis"
        : fitIsOutdated
          ? "Refresh fit"
          : "Analyze fit",
  );

  function score(value: number | null | undefined): string {
    const valid = finiteUnitScore(value);
    return valid !== null ? `${Math.round(valid * 100)}%` : "Not scored";
  }

  /** The Research score is a relative ranking index across this Discovery run,
   *  not a percentage of anything — the ranked list and the header record line
   *  both print it bare, so this row does too. Sub-metrics stay percentages. */
  function indexScore(value: number | null | undefined): string {
    const valid = finiteUnitScore(value);
    return valid !== null ? String(Math.round(valid * 100)) : "Not scored";
  }

  function ideaReference(ideaId: string | undefined, ideaRevision: number | undefined): FounderFitReference | null {
    if (!ideaId) return null;
    return { ideaId, ideaRevision: ideaRevision ?? 1 };
  }

  function founderFitFor(ideaId: string | undefined, ideaRevision: number | undefined) {
    const reference = ideaReference(ideaId, ideaRevision);
    return reference ? founderFitResultFor(fitArtifact, reference) : null;
  }

  const hasBlockingConflict = $derived(data.workspace.ideas.some((idea) => (
    Boolean(founderFitFor(idea.idea_id, idea.idea_revision)?.blockingConflict?.trim())
  )));

  function setFitDetailOpen(key: string, event: Event): void {
    const details = event.currentTarget;
    if (!(details instanceof HTMLDetailsElement)) return;
    openFitDetails = { ...openFitDetails, [key]: details.open };
  }

  function fitDetailBodyId(ideaId: string, ideaRevision: number): string {
    const stableIdeaId = ideaId.replace(/[^a-zA-Z0-9_-]+/g, "-");
    return `fit-reasoning-body-${stableIdeaId}-${ideaRevision}`;
  }

  function profileSummary(): string {
    const profile = data.decisionState?.profile;
    if (!profile) return "No build limits saved yet.";
    return formatBuildConstraints(profile);
  }

  async function analyzeFit(): Promise<void> {
    if (!canMutate) {
      fitError = "This comparison is view-only because idea selection has ended.";
      return;
    }
    if (!data.decisionState?.profile) {
      tools.openConstraints();
      return;
    }
    if (!hasExactScope) {
      fitError = exactScopeError;
      return;
    }
    if (fitRunning) return;

    fitRunning = true;
    fitError = "";
    fitNotice = "";
    try {
      const response = await runFounderFit(data.job.id, scopeReferences);
      if (!founderFitMatchesScope(response.analysis, scopeReferences)) {
        fitError = "The shortlist changed while fit was being analyzed. Review the current ideas and try again.";
        return;
      }
      fitOverride = response.analysis;
      fitNotice = response.cached
        ? "Your saved fit analysis is current for these ideas."
        : `Fit analysis saved for ${scopeReferences.length} selected ${scopeReferences.length === 1 ? "idea" : "ideas"}.`;
      void invalidateAll();
    } catch (cause) {
      fitError = cause instanceof Error
        ? cause.message
        : "Fit analysis could not be completed. Your shortlist was not changed.";
    } finally {
      fitRunning = false;
    }
  }

  function verdictLabel(verdict: FounderFitVerdict | undefined): string {
    if (!verdict) return "Not analyzed";
    return {
      fits: "Fits your build limits",
      needs_reshape: "Could fit with changes",
      blocked: "Conflicts with a build limit",
      insufficient_evidence: "Needs more evidence",
    }[verdict];
  }

  function dimensionLabel(dimension: FounderFitDimension): string {
    return {
      time: "Available time",
      budget: "Testing budget",
      team: "Team",
      revenue_horizon: "Revenue timing",
      distribution: "Reach",
      strengths: "Founder advantage",
      hard_constraints: "Non-negotiables",
    }[dimension];
  }

  function statusLabel(status: FounderFitStatus): string {
    return {
      aligned: "Aligned",
      conflict: "Conflict",
      unknown: "Unknown",
      irrelevant: "Not applicable",
    }[status];
  }

  function reasoningSources(profileFields: string[], ideaFields: string[]): string {
    return founderFitReasoningSources(profileFields, ideaFields);
  }

  function formattedGeneratedAt(): string {
    if (!fitArtifact) return "";
    const createdAt = new Date(fitArtifact.createdAt);
    if (Number.isNaN(createdAt.getTime())) return "Saved analysis";
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(createdAt);
  }

  /** Index of the sole highest-scoring candidate in a row, or -1 on a tie or
   *  when there is nothing to compare — used to mark the row leader. */
  function leaderIndexOf(values: Array<number | null | undefined>): number {
    const nums = values
      .map((value, i) => ({ value: finiteUnitScore(value), i }))
      .filter((entry): entry is { value: number; i: number } => entry.value !== null)
      .map((entry) => ({ v: Math.round(entry.value * 100), i: entry.i }));
    if (nums.length < 2) return -1;
    const max = Math.max(...nums.map((x) => x.v));
    const leaders = nums.filter((x) => x.v === max);
    return leaders.length === 1 ? leaders[0].i : -1;
  }

  function pct(v: number | null | undefined): number {
    const valid = finiteUnitScore(v);
    return valid !== null ? Math.round(valid * 100) : 0;
  }

  function evidenceNote(idea: (typeof data.workspace.ideas)[number]): string {
    const adversarial = adversarialReviewFinding(idea);
    if (adversarial && idea.red_team_verdict?.trim().toLowerCase() !== "survives") {
      return [adversarial.label, ...adversarial.details].join(". ");
    }
    // Pipeline prose carries internal gate names, raw field names and a research
    // vocabulary of its own. This used to be a hand-rolled chain that ended in a blind
    // `\s*[—–]\s*` -> ". " replace — the SAME line `buyerFacingIdeaProse` was extracted to
    // replace after it produced 990 degraded instances on the idea cards (see that
    // module's note). Measured on the 730 distinct values this row actually reads, the
    // chain left 81 residual jargon instances and invented 99 lower-cased sentence starts
    // ("…mechanism. using AI…"); the shared authority leaves 0 of each, keeps parenthetical
    // dash PAIRS intact, and knows the cold-start and corpus vocabulary the chain never had.
    return buyerFacingIdeaProse(
      idea.critic_concern ?? idea.incumbent_parity ?? idea.data_acquisition_notes,
    ) || "No additional evidence note is recorded.";
  }

  type RowKind = "score" | "text" | "narrative";
  const marketRows = $derived.by(() => {
    const ideas = data.workspace.ideas;
    const col = <T,>(get: (i: (typeof ideas)[number]) => T) => ideas.map(get);
    const rows: Array<{ key: string; fallback: string; kind: RowKind; index?: boolean; tooltip?: string; values: Array<number | string | null | undefined> }> = [
      { key: "research_score", fallback: "Research score", kind: "score", index: true, values: col(displayCompositeScore) },
      { key: "market_fit", fallback: "Market fit", kind: "score", values: col((i) => i.market_fit_score) },
      { key: "technical_feasibility", fallback: "Feasibility", kind: "score", values: col((i) => i.technical_feasibility_score) },
      { key: "distribution_seo", fallback: "Distribution / SEO", kind: "score", values: col((i) => i.seo_scalability_score) },
      { key: "originality", fallback: "Distinctiveness", kind: "score", values: col(originalityScore) },
      { key: "build_estimate", fallback: "Build estimate", kind: "text", values: col((i) => i.estimated_development_time ?? "Not available") },
      { key: "evidence_anchor", fallback: "Evidence anchor", kind: "narrative", values: col((i) => i.source_pain ?? i.pain_points_addressed?.[0] ?? "No direct pain anchor is available.") },
      { key: "audience", fallback: "Audience", kind: "narrative", values: col((i) => i.source_segment ?? i.target_personas?.[0] ?? "No audience anchor is available.") },
      { key: "distinctive_wedge", fallback: "Distinctive wedge", kind: "narrative", values: col((i) => i.differentiation_locus ?? i.innovation_angle ?? i.differentiation_factors?.[0] ?? i.value_proposition) },
      // `critic_concern` is a durable calibration note and can be positive or
      // mixed. Real red-team objections still take precedence in the cell.
      { key: "evidence_note", fallback: "Evidence note", kind: "narrative", values: col(evidenceNote) },
    ];
    return rows.map((row) => ({
      ...row,
      leaderIndex: row.kind === "score" ? leaderIndexOf(row.values as Array<number | null | undefined>) : -1,
    }));
  });
</script>

{#snippet metricLabel(key: string, fallback: string, tooltip?: string)}
  {@const explanation = metricMap.get(key)}
  <span class="metric-label-copy">{explanation?.label ?? fallback}</span>
  <!-- The Tooltip wrapper is the single focusable trigger (it carries focus +
       aria-describedby); the inner marker is a plain span so there is exactly
       one tab stop and no dead nested control. -->
  {#if explanation}
    <Tooltip
      content={[
        explanation.summary,
        explanation.caveat,
      ].filter(Boolean).join(" ")}
      position="right"
    >
      {#snippet children()}
        <span class="metric-help">
          <HelpCircle aria-hidden="true" />
        </span>
      {/snippet}
    </Tooltip>
  {:else if tooltip}
    <Tooltip content={tooltip} position="right">
      {#snippet children()}
        <span class="metric-help">
          <HelpCircle aria-hidden="true" />
        </span>
      {/snippet}
    </Tooltip>
  {/if}
{/snippet}

<section class="selection-page">
  <header class="selection-page__header">
    <div>
      <h2 id="compare-title">Compare the ideas you selected</h2>
      <p class="selection-page__lead">
        {#if decisionTools}
          Start with the research evidence, then check how the same ideas fit your time, budget, and team. Switching views never changes a score.
        {:else}
          See how the ideas you selected differ on the research evidence. Comparing never changes a score.
        {/if}
      </p>
    </div>
    {#if decisionTools}
    <div class="compare-switcher">
      <SegmentControl
        options={compareViewOptions}
        value={compareView}
        density="compact"
        label="Comparison view"
        onChange={changeCompareView}
      />
    </div>
    {/if}
  </header>

  {#if viewOnly}
    <p class="selection-page__view-only" role="status">
      View only. Idea selection has ended. You can inspect this comparison and saved fit reasoning, but cannot change the shortlist or run another fit analysis here.
    </p>
  {/if}

  {#if data.workspace.ideas.length < 2}
    <div class="selection-page__panel">
      <EmptyState
        title={viewOnly
          ? data.workspace.ideas.length === 0
            ? "No saved candidate is available to compare"
            : "One idea in the saved comparison"
          : data.workspace.ideas.length === 0
            ? "No candidate is available to compare"
            : "Add a second idea to compare"}
        description={viewOnly
          ? data.workspace.ideas.length === 0
            ? "This run has no current candidate revision in its saved comparison record."
            : "A side-by-side comparison was not saved for this run."
          : data.workspace.ideas.length === 0
            ? "Return to the ranked ideas and choose a current idea revision."
            : "Comparing trade-offs needs at least two ideas. Add a second idea to your shortlist, then compare them side by side."}
      >
        <Button
          href={rankedIdeasHref}
          class="btn-ghost"
          label="Back to ranked ideas"
        />
      </EmptyState>
    </div>
  {:else}
    <div
      class="comparison selection-page__panel"
      role="region"
      aria-labelledby="compare-title"
      style={`--candidate-count: ${Math.max(data.workspace.ideas.length, 1)}`}
    >
      <div class="comparison-label header-label">Candidate</div>
      {#each data.workspace.ideas as idea, index}
        <article class="candidate-heading">
          <small>
            Candidate {index + 1} · revision {idea.idea_revision ?? 1}
          </small>
          <h3>{solutionDisplayTitle(idea)}</h3>
          <!-- Without this the review's finding only reached the evidence-note row far
               below, so a candidate whose premise the review could not confirm read as a
               peer of the survivors at the top of its own column. -->
          {#if isPremiseUnproven(idea)}
            {@const finding = adversarialReviewFinding(idea)}
            <Tooltip
              content={finding ? adversarialReviewSummary(finding) : PREMISE_UNPROVEN_LABEL}
              position="bottom"
            >
              {#snippet children()}
                <span class="premise-flag">{PREMISE_UNPROVEN_LABEL}</span>
              {/snippet}
            </Tooltip>
          {/if}
          <p>{idea.short_description ?? idea.description}</p>
        </article>
      {/each}

      {#if compareView === "market"}
        {#each marketRows as row (row.key)}
          <div class="comparison-label">{@render metricLabel(row.key, row.fallback, row.tooltip)}</div>
          {#each row.values as v, i}
            <div
              class="comparison-value"
              class:metric-cell={row.kind === "score"}
              class:narrative={row.kind === "narrative"}
              class:is-leader={i === row.leaderIndex}
              role="group"
              aria-label={`${solutionDisplayTitle(data.workspace.ideas[i])}, ${metricMap.get(row.key)?.label ?? row.fallback}: ${row.kind === "score" ? (row.index ? indexScore(v as number) : score(v as number)) : String(v ?? "Not available")}`}
            >
              {#if row.kind === "score"}
                <span class="bar" aria-hidden="true"><span class="bar-fill" style={`width:${pct(v as number)}%`}></span></span>
                <span class="metric-num">{row.index ? indexScore(v as number) : score(v as number)}</span>
                {#if i === row.leaderIndex}
                  <Tooltip content={LEADER_EXPLANATION} position="bottom">
                    {#snippet children()}<Badge variant="default" size="sm">Leads</Badge>{/snippet}
                  </Tooltip>
                {/if}
              {:else}
                {v}
              {/if}
            </div>
          {/each}
        {/each}
      {:else}
        <div class="comparison-label">Your saved lens</div>
        {#each data.workspace.ideas as idea}<div class="comparison-value narrative" role="group" aria-label={`${solutionDisplayTitle(idea)}, your saved lens: ${profileSummary()}`}>{profileSummary()}</div>{/each}
        <div class="comparison-label">Fit verdict</div>
        {#each data.workspace.ideas as idea}
          {@const result = founderFitFor(idea.idea_id, idea.idea_revision)}
          <div class="comparison-value verdict" role="group" aria-label={`${solutionDisplayTitle(idea)}, fit verdict: ${verdictLabel(result?.verdict)}`}>
            <span class:fit-verdict={Boolean(result)} class:fit-verdict--fits={result?.verdict === "fits"} class:fit-verdict--needs-reshape={result?.verdict === "needs_reshape"} class:fit-verdict--blocked={result?.verdict === "blocked"} class:fit-verdict--insufficient={result?.verdict === "insufficient_evidence"}>
              {verdictLabel(result?.verdict)}
            </span>
          </div>
        {/each}
        <div class="comparison-label">Why it fits or does not</div>
        {#each data.workspace.ideas as idea}<div class="comparison-value narrative" role="group" aria-label={`${solutionDisplayTitle(idea)}, fit summary: ${founderFitFor(idea.idea_id, idea.idea_revision)?.summary ?? "Analyze fit against your saved build limits first."}`}>{founderFitFor(idea.idea_id, idea.idea_revision)?.summary ?? "Analyze fit against your saved build limits first."}</div>{/each}
        <div class="comparison-label">Strongest advantage</div>
        {#each data.workspace.ideas as idea}<div class="comparison-value narrative" role="group" aria-label={`${solutionDisplayTitle(idea)}, strongest advantage: ${founderFitFor(idea.idea_id, idea.idea_revision)?.strongestAdvantage ?? "Not available"}`}>{founderFitFor(idea.idea_id, idea.idea_revision)?.strongestAdvantage ?? "Not available"}</div>{/each}
        {#if hasBlockingConflict}
          <div class="comparison-label">Blocking conflict</div>
          {#each data.workspace.ideas as idea}<div class="comparison-value narrative" role="group" aria-label={`${solutionDisplayTitle(idea)}, blocking conflict: ${founderFitFor(idea.idea_id, idea.idea_revision)?.blockingConflict ?? "No blocking conflict recorded."}`}>{founderFitFor(idea.idea_id, idea.idea_revision)?.blockingConflict ?? "No blocking conflict recorded."}</div>{/each}
        {/if}
        <div class="comparison-label">Decision-changing unknown</div>
        {#each data.workspace.ideas as idea}<div class="comparison-value narrative" role="group" aria-label={`${solutionDisplayTitle(idea)}, decision-changing unknown: ${founderFitFor(idea.idea_id, idea.idea_revision)?.decisionChangingUnknown ?? "This candidate still needs a fit analysis."}`}>{founderFitFor(idea.idea_id, idea.idea_revision)?.decisionChangingUnknown ?? "This candidate still needs a fit analysis."}</div>{/each}
      {/if}
    </div>

    <!-- Quiet escape hatch: the branch tool was otherwise unreachable from compare.
         Gated — without the grant openVariants() is a no-op, so this would render as a
         permanently dead button. -->
    {#if decisionTools && canMutate}
      <p class="branch-escape">
        <button type="button" class="branch-escape__action" onclick={() => tools.openVariants()}>
          None of these fit? Branch a new direction →
        </button>
      </p>
    {/if}

    {#if compareView === "founder"}
      <aside class:fit-action--current={Boolean(fitArtifact)} class="fit-action" aria-labelledby="fit-action-title">
        <div class="fit-action__copy">
          <span class="fit-action__eyebrow">Fit analysis</span>
          <strong id="fit-action-title">
            {#if !data.decisionState?.profile}
              Add your build limits
            {:else if fitRunning}
              Checking these ideas against your build limits…
            {:else if fitArtifact}
              Fit analysis is current for this shortlist
            {:else if fitIsOutdated}
              Your shortlist or build limits changed
            {:else}
              See which ideas fit the way you can build
            {/if}
          </strong>
          <p>
            {#if !data.decisionState?.profile}
              Save your available time, testing budget, team, and advantages before comparing personal fit.
            {:else if fitArtifact}
              Generated {formattedGeneratedAt()} · Private to you · Research scores stay unchanged.
            {:else if fitIsOutdated}
              Refresh the analysis before using it to compare these exact idea revisions.
            {:else}
              This checks the selected ideas against your time, budget, team, reach, and non-negotiables. It never changes their research scores.
            {/if}
          </p>
        </div>
        <SubmitButton
          type="button"
          label={fitButtonLabel}
          loadingText="Analyzing…"
          loading={fitRunning}
          disabled={!canMutate || fitRunning || (Boolean(data.decisionState?.profile) && !hasExactScope)}
          minWidth="11rem"
          class=""
          title={!hasExactScope && data.decisionState?.profile ? "Reload the shortlist to restore exact idea revision references." : undefined}
          describedBy={fitError || exactScopeError ? "fit-analysis-error" : undefined}
          onclick={() => void analyzeFit()}
        />
      </aside>

      <div class="fit-feedback" aria-live="polite" aria-atomic="true">
        {#if fitError}<p id="fit-analysis-error" class="fit-feedback__error" role="alert">{fitError}</p>{/if}
        {#if !fitError && exactScopeError}<p id="fit-analysis-error" class="fit-feedback__error">{exactScopeError}</p>{/if}
        {#if fitNotice}<p class="fit-feedback__notice" role="status">{fitNotice}</p>{/if}
      </div>

      {#if fitArtifact}
        <section class="fit-reasoning" aria-labelledby="fit-reasoning-title">
          <header class="fit-reasoning__header">
            <div>
              <span class="fit-action__eyebrow">Reasoning</span>
              <h3 id="fit-reasoning-title">Inspect what shaped each fit call</h3>
              <p>Open a candidate to see the constraint-by-constraint reasoning and what could change the call.</p>
            </div>
            <span class="fit-reasoning__record">{fitArtifact.results.length} exact {fitArtifact.results.length === 1 ? "revision" : "revisions"}</span>
          </header>

          <div class="fit-reasoning__list">
            {#each data.workspace.ideas as idea, index (`${idea.idea_id}:${idea.idea_revision ?? 1}`)}
                {@const result = founderFitFor(idea.idea_id, idea.idea_revision)}
              {#if result}
                {@const detailKey = `${idea.idea_id}:${idea.idea_revision ?? 1}`}
                {@const detailBodyId = fitDetailBodyId(result.ideaId, result.ideaRevision)}
                <details
                  class="fit-detail"
                  open={Boolean(openFitDetails[detailKey])}
                  ontoggle={(event) => setFitDetailOpen(detailKey, event)}
                >
                  <summary
                    aria-expanded={Boolean(openFitDetails[detailKey])}
                    aria-controls={detailBodyId}
                  >
                    <span class="fit-detail__identity">
                      <small>Candidate {index + 1} · revision {idea.idea_revision ?? 1}</small>
                      <strong>{solutionDisplayTitle(idea)}</strong>
                    </span>
                    <span class="fit-detail__summary-status">{verdictLabel(result.verdict)}</span>
                    <ChevronDown class="fit-detail__chevron" aria-hidden="true" />
                  </summary>
                  <div class="fit-detail__body" id={detailBodyId}>
                    <div class="fit-detail__callout">
                      <div>
                        <h4>What could change this call</h4>
                        <p>{result.sensitivity}</p>
                      </div>
                      <div>
                        <h4>Decision-changing unknown</h4>
                        <p>{result.decisionChangingUnknown}</p>
                      </div>
                    </div>

                    <ul class="fit-dimensions" aria-label={`Fit reasoning for ${solutionDisplayTitle(idea)}`}>
                      {#each result.dimensions as dimension (dimension.dimension)}
                        <li>
                          <div class="fit-dimension__heading">
                            <strong>{dimensionLabel(dimension.dimension)}</strong>
                            <span class="dimension-status dimension-status--{dimension.status}">{statusLabel(dimension.status)}</span>
                          </div>
                          <p>{dimension.summary}</p>
                          <small>Based on {reasoningSources(dimension.profileFields, dimension.ideaFields)}</small>
                        </li>
                      {/each}
                    </ul>

                    <div class="fit-next-test">
                      <div>
                        <span class="fit-action__eyebrow">Next question</span>
                        <h4>{result.suggestedExperiment.assumption}</h4>
                        <p>{result.suggestedExperiment.whyCritical}</p>
                      </div>
                      {#if canMutate}
                        <button
                          type="button"
                          onclick={() => tools.openTestPlanner({
                            ideaId: result.ideaId,
                            ideaRevision: result.ideaRevision,
                            assumptionId: result.suggestedExperiment.assumptionId ?? undefined,
                            draft: result.suggestedExperiment,
                          })}
                        >Plan a test</button>
                      {/if}
                    </div>
                  </div>
                </details>
              {/if}
            {/each}
          </div>
        </section>
      {/if}
    {/if}
  {/if}
</section>

<style>
  .selection-page__view-only {
    max-width: 72ch;
    margin: 0;
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-bg-surface);
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: var(--leading-normal);
  }
  .comparison {
    display: grid;
    grid-template-columns: minmax(var(--space-30), 0.48fr) repeat(var(--candidate-count, 2), minmax(0, 1fr));
    overflow: hidden;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-bg-elevated);
  }
  .comparison > * {
    min-width: 0;
    padding: var(--space-3) var(--space-4);
    border-bottom: 1px solid var(--color-border);
    overflow-wrap: anywhere;
  }

  .header-label {
    color: var(--color-text-muted);
    font: 700 var(--text-11)/var(--leading-tight) var(--font-mono);
    letter-spacing: var(--tracking-wider);
    text-transform: uppercase;
  }
  .candidate-heading {
    min-height: var(--space-30);
    padding-top: var(--space-4);
    padding-bottom: var(--space-4);
    background: var(--color-bg-surface);
  }
  .candidate-heading small {
    color: var(--color-text-muted);
    font: 700 var(--text-xs)/var(--leading-tight) var(--font-mono);
    letter-spacing: var(--tracking-widest);
    text-transform: uppercase;
  }
  .candidate-heading h3 {
    margin: var(--space-2) 0 0;
    font-family: var(--font-display);
    font-size: var(--text-md);
    font-weight: 700;
    line-height: var(--leading-snug);
    letter-spacing: var(--tracking-tight);
    text-wrap: pretty;
  }
  /* Matches the risk chip SelectionWorkbench already uses for this same finding. */
  .premise-flag {
    display: inline-flex;
    align-items: center;
    margin-top: var(--space-2);
    padding: 0.09rem 0.34rem;
    border: 1px solid color-mix(in srgb, var(--color-error) 30%, transparent);
    border-radius: var(--radius-md);
    background: var(--color-error-subtle);
    color: var(--color-error-text);
    font-family: var(--font-body);
    font-size: var(--text-xs);
    font-weight: 700;
  }
  .candidate-heading p {
    display: -webkit-box;
    overflow: hidden;
    margin: var(--space-2) 0 0;
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    line-height: var(--leading-normal);
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    line-clamp: 2;
  }

  .comparison-label {
    display: flex;
    gap: var(--space-2);
    align-items: center;
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    font-weight: 700;
    line-height: var(--leading-snug);
  }
  .metric-label-copy { min-width: 0; }
  .metric-help {
    display: grid;
    flex: 0 0 auto;
    width: var(--space-6);
    height: var(--space-6);
    padding: 0;
    place-items: center;
    border: 0;
    border-radius: var(--radius-full);
    color: var(--color-text-muted);
    background: transparent;
    cursor: help;
    transition: color var(--duration-fast) var(--ease-default), background var(--duration-fast) var(--ease-default), transform var(--duration-fast) var(--ease-default);
  }
  .metric-help:hover { color: var(--color-text-secondary); background: var(--color-bg-surface); }
  .metric-help:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  .metric-help:active { transform: scale(0.94); }
  .metric-help :global(svg) { width: var(--space-3); height: var(--space-3); }

  .comparison-value {
    color: var(--color-text-primary);
    font-size: var(--text-base);
    font-weight: 600;
    line-height: var(--leading-normal);
  }

  .metric-cell { display: flex; align-items: center; gap: var(--space-2); }
  .bar {
    flex: 1;
    min-width: var(--space-8);
    max-width: calc(var(--space-20) + var(--space-16));
    height: var(--space-1-5);
    overflow: hidden;
    border-radius: var(--radius-full);
    background: var(--color-bg-surface);
    box-shadow: inset 0 0 0 1px var(--color-border);
  }
  .bar-fill { display: block; height: 100%; border-radius: var(--radius-full); background: var(--color-text-muted); }
  .metric-num { flex: 0 0 auto; min-width: var(--space-10); color: var(--color-text-secondary); font-variant-numeric: tabular-nums; font-weight: 600; }
  .is-leader .bar-fill { background: var(--color-text-primary); }
  .is-leader .metric-num { color: var(--color-text-primary); font-weight: 800; }

  .narrative { color: var(--color-text-secondary); font-size: var(--text-13); font-weight: 400; line-height: var(--leading-normal); text-wrap: pretty; }

  .branch-escape { margin: var(--space-3) 0 0; text-align: right; }
  .branch-escape__action {
    padding: var(--space-1) 0;
    border: 0;
    background: transparent;
    color: var(--color-text-muted);
    font-family: var(--font-body);
    font-size: var(--text-13);
    font-weight: 600;
    cursor: pointer;
    transition: color var(--duration-fast) var(--ease-default);
  }
  .branch-escape__action:hover { color: var(--color-text-primary); text-decoration: underline; text-underline-offset: var(--space-1); }
  .branch-escape__action:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  .fit-verdict {
    display: inline-flex;
    align-items: center;
    min-height: var(--space-6);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-full);
    font-size: var(--text-11);
    font-weight: 700;
  }
  .fit-verdict--fits { color: var(--color-success-text); background: var(--color-success-subtle); }
  .fit-verdict--needs-reshape, .fit-verdict--insufficient { color: var(--color-warning-text); background: var(--color-warning-subtle); }
  .fit-verdict--blocked { color: var(--color-error-text); background: var(--color-error-subtle); }

  /* Shared emphasis-card recipe (finding: one accent tint token + border-accent
     + shadow-sm), matched by the review page's .confirm-card. */
  .fit-action {
    display: flex;
    justify-content: space-between;
    gap: var(--space-6);
    align-items: center;
    margin-top: var(--space-4);
    padding: var(--space-5);
    border: 1px solid var(--color-border-accent);
    border-radius: var(--radius-lg);
    background: var(--color-accent-subtle);
    box-shadow: var(--shadow-sm);
  }
  .fit-action--current { border-color: var(--color-border); background: var(--color-bg-elevated); }
  .fit-action__copy { min-width: 0; }
  .fit-action__eyebrow {
    display: block;
    margin-bottom: var(--space-1);
    color: var(--color-text-muted);
    font: 700 var(--text-xs)/var(--leading-tight) var(--font-mono);
    letter-spacing: var(--tracking-wider);
    text-transform: uppercase;
  }
  .fit-action strong, .fit-action p { display: block; margin: 0; }
  .fit-action strong { font-family: var(--font-display); font-size: var(--text-md); font-weight: 700; }
  .fit-action p { max-width: 64ch; margin-top: var(--space-1); color: var(--color-text-secondary); font-size: var(--text-base); line-height: var(--leading-normal); }

  .fit-feedback:empty { display: none; }
  .fit-feedback p { margin: var(--space-3) 0 0; padding: var(--space-3) var(--space-4); border-radius: var(--radius-md); font-size: var(--text-13); line-height: var(--leading-normal); }
  .fit-feedback__error { color: var(--color-error-text); background: var(--color-error-subtle); }
  .fit-feedback__notice { color: var(--color-success-text); background: var(--color-success-subtle); }

  .fit-reasoning {
    margin-top: var(--space-6);
    overflow: hidden;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-bg-elevated);
    box-shadow: var(--shadow-sm);
  }
  .fit-reasoning__header {
    display: flex;
    justify-content: space-between;
    gap: var(--space-6);
    align-items: start;
    padding: var(--space-5);
    border-bottom: 1px solid var(--color-border);
  }
  .fit-reasoning__header h3 { margin: 0; font-family: var(--font-display); font-size: var(--text-xl); font-weight: 700; letter-spacing: var(--tracking-tight); }
  .fit-reasoning__header p { max-width: 64ch; margin: var(--space-2) 0 0; color: var(--color-text-secondary); font-size: var(--text-base); line-height: var(--leading-normal); }
  .fit-reasoning__record { flex: 0 0 auto; color: var(--color-text-muted); font: 700 var(--text-11)/var(--leading-tight) var(--font-mono); letter-spacing: var(--tracking-wide); text-transform: uppercase; }
  .fit-reasoning__list { display: grid; }

  .fit-detail + .fit-detail { border-top: 1px solid var(--color-border); }
  .fit-detail summary {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto auto;
    gap: var(--space-4);
    align-items: center;
    min-height: var(--space-20);
    padding: var(--space-4) var(--space-5);
    list-style: none;
    cursor: pointer;
    transition: background var(--duration-fast) var(--ease-default);
  }
  .fit-detail summary::-webkit-details-marker { display: none; }
  .fit-detail summary:hover { background: var(--color-bg-surface); }
  .fit-detail summary:focus-visible { outline: 2px solid var(--color-accent); outline-offset: -2px; }
  .fit-detail summary:active { background: var(--color-bg-hover); }
  .fit-detail__identity { display: grid; gap: var(--space-1); min-width: 0; }
  .fit-detail__identity small { color: var(--color-text-muted); font: 700 var(--text-xs)/var(--leading-tight) var(--font-mono); letter-spacing: var(--tracking-wide); text-transform: uppercase; }
  .fit-detail__identity strong { overflow: hidden; font-family: var(--font-display); font-size: var(--text-md); font-weight: 700; line-height: var(--leading-snug); text-overflow: ellipsis; white-space: nowrap; }
  .fit-detail__summary-status { color: var(--color-text-secondary); font-size: var(--text-13); font-weight: 700; }
  .fit-detail__chevron { width: var(--space-4); height: var(--space-4); color: var(--color-text-muted); transition: transform var(--duration-normal) var(--ease-default); }
  .fit-detail[open] .fit-detail__chevron { transform: rotate(180deg); }
  .fit-detail__body { padding: 0 var(--space-5) var(--space-5); }
  .fit-detail__callout { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-bg-surface); }
  .fit-detail__callout > div { padding: var(--space-4); }
  .fit-detail__callout > div + div { border-left: 1px solid var(--color-border); }
  .fit-detail__callout h4, .fit-detail__callout p { margin: 0; }
  .fit-detail__callout h4 { font-size: var(--text-13); font-weight: 700; }
  .fit-detail__callout p { margin-top: var(--space-1); color: var(--color-text-secondary); font-size: var(--text-13); line-height: var(--leading-normal); }

  .fit-dimensions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-3); margin: var(--space-4) 0 0; padding: 0; list-style: none; }
  .fit-dimensions li { padding: var(--space-4); border: 1px solid var(--color-border); border-radius: var(--radius-md); }
  .fit-dimension__heading { display: flex; justify-content: space-between; gap: var(--space-3); align-items: center; }
  .fit-dimension__heading strong { font-size: var(--text-13); font-weight: 700; }
  .dimension-status { flex: 0 0 auto; padding: var(--space-1) var(--space-2); border-radius: var(--radius-full); font-size: var(--text-xs); font-weight: 700; }
  .dimension-status--aligned { color: var(--color-success-text); background: var(--color-success-subtle); }
  .dimension-status--conflict { color: var(--color-error-text); background: var(--color-error-subtle); }
  .dimension-status--unknown { color: var(--color-warning-text); background: var(--color-warning-subtle); }
  .dimension-status--irrelevant { color: var(--color-text-secondary); background: var(--color-bg-surface); }
  .fit-dimensions p { margin: var(--space-2) 0 0; color: var(--color-text-secondary); font-size: var(--text-13); line-height: var(--leading-normal); }
  .fit-dimensions small { display: block; margin-top: var(--space-2); color: var(--color-text-muted); font-size: var(--text-11); line-height: var(--leading-normal); }

  .fit-next-test { display: flex; justify-content: space-between; gap: var(--space-6); align-items: center; margin-top: var(--space-4); padding: var(--space-4); border-radius: var(--radius-md); background: var(--color-bg-surface); }
  .fit-next-test h4, .fit-next-test p { margin: 0; }
  .fit-next-test h4 { font-size: var(--text-base); font-weight: 700; }
  .fit-next-test p { margin-top: var(--space-1); color: var(--color-text-secondary); font-size: var(--text-13); line-height: var(--leading-normal); }
  .fit-next-test button { flex: 0 0 auto; min-height: var(--space-10); padding: var(--space-2) var(--space-4); border: 1px solid var(--color-input-border); border-radius: var(--radius-md); color: var(--color-text-primary); background: var(--color-bg-elevated); font: inherit; font-size: var(--text-13); font-weight: 700; cursor: pointer; transition: border-color var(--duration-fast) var(--ease-default), background var(--duration-fast) var(--ease-default), transform var(--duration-fast) var(--ease-default); }
  .fit-next-test button:hover { border-color: var(--color-input-border-hover); background: var(--color-bg-hover); }
  .fit-next-test button:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  .fit-next-test button:active { transform: scale(0.98); }

  @media (max-width: 767px) {
    .comparison {
      grid-template-columns: minmax(var(--space-30), 0.7fr) repeat(var(--candidate-count, 2), minmax(var(--space-35), 1fr));
      overflow-x: auto;
      overscroll-behavior-inline: contain;
      scrollbar-width: thin;
    }
    .comparison-label { position: sticky; left: 0; z-index: 1; background: var(--color-bg-surface); box-shadow: 1px 0 0 var(--color-border); }
    .candidate-heading { min-height: calc(var(--space-30) + var(--space-6)); }
    .bar { max-width: none; }
    .fit-action { align-items: flex-start; flex-direction: column; }
    .fit-reasoning__header { display: block; }
    .fit-reasoning__record { display: block; margin-top: var(--space-3); }
    .fit-detail summary { grid-template-columns: minmax(0, 1fr) auto; }
    .fit-detail__summary-status { grid-column: 1; grid-row: 2; }
    .fit-detail__chevron { grid-column: 2; grid-row: 1 / span 2; }
    .fit-detail__callout, .fit-dimensions { grid-template-columns: 1fr; }
    .fit-detail__callout > div + div { border-top: 1px solid var(--color-border); border-left: 0; }
    .fit-next-test { align-items: flex-start; flex-direction: column; }
    .fit-next-test button { width: 100%; }
  }

  @media (prefers-reduced-motion: reduce) {
    .metric-help,
    .metric-help:active,
    .fit-detail summary,
    .fit-detail__chevron,
    .fit-detail[open] .fit-detail__chevron,
    .fit-next-test button,
    .fit-next-test button:active {
      transition: none;
      transform: none;
    }
  }
</style>
