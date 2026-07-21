<script lang="ts">
  import { FlaskConical, Loader2, MessageSquare, X } from "lucide-svelte";
  import {
    createFounderFitReshapeProposal,
    getFounderFit,
    getFounderFitReshapeProposal,
    runFounderFit,
  } from "$lib/api";
  import type { IdeaSynthesisPatch, SeedResultSummary, SynthesisOperation } from "$lib/api";
  import AnnotationSurface from "$lib/components/annotations/AnnotationSurface.svelte";
  import AssumptionMap from "$lib/components/selection/AssumptionMap.svelte";
  import DecisionRiskQueue from "$lib/components/selection/DecisionRiskQueue.svelte";
  import EvidenceChallenge from "$lib/components/selection/EvidenceChallenge.svelte";
  import ReshapeProposalPanel from "$lib/components/selection/ReshapeProposalPanel.svelte";
  import DecisionHelp from "$lib/components/ui/DecisionHelp.svelte";
  import WorkspaceOverlay from "$lib/components/ui/WorkspaceOverlay.svelte";
  import type { FounderFitArtifact, FounderFitResult, FounderFitVerdict } from "$lib/types/founderFit";
  import type { SelectionDecisionProfile, SolutionPreview } from "$lib/types/job";
  import type { SelectionExperimentDraftSeed } from "$lib/types/selectionExperiment";
  import type {
    SelectionAssumptionPrefill,
    SelectionOwnerEvidencePrefill,
  } from "$lib/types/selectionCopilot";
  import type { SelectionChallengeLens } from "$lib/types/selectionChallenge";
  import {
    ASK_ANALYST_LABEL,
    COCKPIT_GROUP_COPY,
    COCKPIT_GROUP_MODES,
    COCKPIT_SCOPE_LABEL,
    cockpitScopeLine,
    DRAFT_TEST_BRIEF_LABEL,
    founderContextLabel,
    type CockpitMode,
    type CockpitTabGroup,
  } from "$lib/selection/labels";
  import { computeCompositeScore, solutionDisplayTitle } from "$lib/utils/solution-utils";

  interface Props {
    open: boolean;
    jobId?: string;
    ideas: SolutionPreview[];
    profile?: SelectionDecisionProfile | null;
    initialMode?: CockpitMode;
    /** Which tab group is shown: Compare (market/fit) or Pressure-test
     *  (evidence check/decision risks/assumption map). Defaults to Compare. */
    tabGroup?: CockpitTabGroup;
    initialChallengeFocus?: {
      requestId: number;
      ideaId: string;
      ideaRevision: number;
      lens: SelectionChallengeLens;
      challengeId?: string;
      questionId?: string;
    } | null;
    assumptionPrefill?: SelectionAssumptionPrefill | null;
    ownerEvidencePrefill?: SelectionOwnerEvidencePrefill | null;
    comparisonContext?: {
      dialogLabel: string;
      title: string;
      intro: string;
      regionLabel: string;
    } | null;
    shortlistedIdeaKeys?: string[];
    shortlistAtCapacity?: boolean;
    shortlistDisabled?: boolean;
    onToggleShortlist?: (idea: SolutionPreview) => void;
    variantReview?: {
      operation: SynthesisOperation;
      changeSummary: string;
      sourceContributions: string[];
      requiresValidation: string[];
      conclusionOutcome: "FAIL" | "AMBIGUOUS" | null;
    } | null;
    onUseVariant?: () => { ok: boolean; message?: string };
    onOpenFounderContext?: () => void;
    onAskAnalyst?: (
      mode: CockpitMode,
      ideas: SolutionPreview[],
    ) => void;
    onClose: () => void;
    onTestUnknown?: (draft: SelectionExperimentDraftSeed) => void;
    /** Opens the concept forge from a challenge finding. Only passed when the
     *  forge is available (same availability as the Shape tile). */
    onShapeAdjacent?: () => void;
    seedCost?: number | null;
    onEvaluateFitReshape?: (patch: IdeaSynthesisPatch, sourceMessageId: string) => Promise<boolean>;
    onReviewFitReshape?: (
      patch: IdeaSynthesisPatch,
      child: SeedResultSummary,
      sourceMessageId: string,
    ) => { ok: boolean; message?: string };
    onUseFitReshape?: (
      patch: IdeaSynthesisPatch,
      child: SeedResultSummary,
      sourceMessageId: string,
    ) => { ok: boolean; message?: string };
  }

  let {
    open,
    jobId,
    ideas,
    profile = null,
    initialMode = "market",
    tabGroup = "compare",
    initialChallengeFocus = null,
    assumptionPrefill = null,
    ownerEvidencePrefill = null,
    comparisonContext = null,
    shortlistedIdeaKeys = [],
    shortlistAtCapacity = false,
    shortlistDisabled = false,
    onToggleShortlist,
    variantReview = null,
    onUseVariant,
    onOpenFounderContext,
    onAskAnalyst,
    onClose,
    onTestUnknown,
    onShapeAdjacent,
    seedCost = null,
    onEvaluateFitReshape,
    onReviewFitReshape,
    onUseFitReshape,
  }: Props = $props();
  let fit = $state<FounderFitArtifact | null>(null);
  let fitLoading = $state(false);
  let fitRunning = $state(false);
  let fitStale = $state(false);
  let fitError = $state("");
  let loadedKey = $state("");
  let mode = $state<CockpitMode>("market");
  let challengeFocus = $state<{
    requestId: number;
    ideaId: string;
    ideaRevision: number;
    lens: SelectionChallengeLens;
    challengeId?: string;
    questionId?: string;
  } | null>(null);
  let tableScrollEl = $state<HTMLDivElement>();
  let wasOpen = $state(false);
  /** Assumption draft built from a challenge finding ("Track as risk"). Lives
   *  here so the path stays inside the open cockpit: the challenge tab hands
   *  the draft over and the assumptions tab receives it as a prefill. */
  let trackRiskPrefill = $state<SelectionAssumptionPrefill | null>(null);
  let seenAssumptionPrefillId = $state("");
  const cockpitModes = $derived(COCKPIT_GROUP_MODES[tabGroup]);
  const gc = $derived(COCKPIT_GROUP_COPY[tabGroup]);

  /** Owner-picked candidate for the per-candidate views (Evidence check). The
   *  scope strip is the single switching surface; EvidenceChallenge keeps its
   *  internal state and follows this via its `candidateId` prop. */
  let scopeCandidateId = $state("");
  const challengeCandidateId = $derived.by(() => {
    if (scopeCandidateId && ideas.some((idea) => ideaKey(idea) === scopeCandidateId)) {
      return scopeCandidateId;
    }
    return ideas[0] ? ideaKey(ideas[0]) : "";
  });

  function handleScopeKeydown(event: KeyboardEvent, currentKey: string) {
    const keys = ideas.map(ideaKey);
    const currentIndex = keys.indexOf(currentKey);
    let nextIndex = currentIndex;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") nextIndex = (currentIndex + 1) % keys.length;
    else if (event.key === "ArrowLeft" || event.key === "ArrowUp") nextIndex = (currentIndex - 1 + keys.length) % keys.length;
    else if (event.key === "Home") nextIndex = 0;
    else if (event.key === "End") nextIndex = keys.length - 1;
    else return;
    event.preventDefault();
    scopeCandidateId = keys[nextIndex];
    queueMicrotask(() => document.getElementById(`cockpit-scope-${nextIndex}`)?.focus());
  }

  function selectMode(nextMode: CockpitMode) {
    mode = nextMode;
  }

  function handleModeKeydown(event: KeyboardEvent, currentMode: CockpitMode) {
    const currentIndex = cockpitModes.indexOf(currentMode);
    let nextIndex = currentIndex;
    if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % cockpitModes.length;
    else if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + cockpitModes.length) % cockpitModes.length;
    else if (event.key === "Home") nextIndex = 0;
    else if (event.key === "End") nextIndex = cockpitModes.length - 1;
    else return;
    event.preventDefault();
    const nextMode = cockpitModes[nextIndex];
    mode = nextMode;
    queueMicrotask(() => document.getElementById(`cockpit-tab-${nextMode}`)?.focus());
  }

  let variantActionMessage = $state("");
  let variantActionFailed = $state(false);
  $effect(() => {
    if (open && !wasOpen) {
      mode = cockpitModes.includes(initialMode) ? initialMode : cockpitModes[0];
      challengeFocus = initialChallengeFocus;
      scopeCandidateId = initialChallengeFocus?.ideaId ?? "";
      trackRiskPrefill = null;
    }
    wasOpen = open;
  });

  // A copilot assumption draft arriving while the cockpit is open supersedes a
  // pending track-as-risk draft; AssumptionMap dedupes applied requestIds.
  $effect(() => {
    const requestId = assumptionPrefill?.requestId ?? "";
    if (requestId && requestId !== seenAssumptionPrefillId) trackRiskPrefill = null;
    seenAssumptionPrefillId = requestId;
  });

  $effect(() => {
    if (tabGroup !== "pressure") return;
    if (!open || !initialChallengeFocus) return;
    if (challengeFocus?.requestId === initialChallengeFocus.requestId) return;
    challengeFocus = initialChallengeFocus;
    scopeCandidateId = initialChallengeFocus.ideaId;
    mode = "challenge";
  });

  const ideaRevisionKey = $derived(
    ideas.map((idea) => `${idea.idea_id ?? idea.solution_name}:${idea.idea_revision ?? 1}`).join("|"),
  );
  const cockpitSurfaceKey = $derived(
    `selection:decision-cockpit:${variantReview ? `variant:${variantReview.operation}` : "shortlist"}:${ideaRevisionKey}`,
  );

  $effect(() => {
    if (!open || mode !== "market" || !tableScrollEl) return;
    void ideaRevisionKey;
    tableScrollEl.scrollLeft = 0;
  });

  $effect(() => {
    const key = open && jobId && profile
      ? `${jobId}:${ideaRevisionKey}:${JSON.stringify(profile)}`
      : "";
    if (!key) {
      loadedKey = "";
      return;
    }
    if (key === loadedKey) return;
    loadedKey = key;
    void loadFit();
  });

  function fitMatchesIdeas(artifact: FounderFitArtifact): boolean {
    if (artifact.results.length !== ideas.length) return false;
    return ideas.every((idea) => artifact.results.some((result) =>
      result.ideaId === (idea.idea_id ?? idea.solution_name)
      && result.ideaRevision === (idea.idea_revision ?? 1)
    ));
  }

  async function loadFit() {
    if (!jobId || !profile) return;
    fitLoading = true;
    fitError = "";
    try {
      const response = await getFounderFit(jobId);
      const matches = response.analysis && fitMatchesIdeas(response.analysis);
      fit = matches ? response.analysis : null;
      fitStale = response.stale || Boolean(response.analysis && !matches);
    } catch (cause) {
      fitError = cause instanceof Error ? cause.message : "Could not load founder-fit guidance.";
    } finally {
      fitLoading = false;
    }
  }

  async function analyzeFit() {
    if (!jobId || !profile || fitRunning) return;
    const references = ideas.flatMap((idea) => idea.idea_id ? [{
      ideaId: idea.idea_id,
      ideaRevision: idea.idea_revision ?? 1,
    }] : []);
    if (references.length !== ideas.length) {
      fitError = "These ideas are missing stable references. Reload the research before analyzing fit.";
      return;
    }

    fitRunning = true;
    fitError = "";
    try {
      const response = await runFounderFit(jobId, references);
      fit = response.analysis;
      fitStale = false;
    } catch (cause) {
      fitError = cause instanceof Error ? cause.message : "Could not analyze founder fit.";
    } finally {
      fitRunning = false;
    }
  }

  function verdictLabel(verdict: FounderFitVerdict): string {
    return {
      fits: "Fits your context",
      needs_reshape: "Reshape first",
      blocked: "Blocked by a constraint",
      insufficient_evidence: "Needs evidence",
    }[verdict];
  }

  function resultFor(idea: SolutionPreview): FounderFitResult | null {
    return fit?.results.find((result) =>
      result.ideaId === (idea.idea_id ?? idea.solution_name)
      && result.ideaRevision === (idea.idea_revision ?? 1)
    ) ?? null;
  }

  const percent = (value?: number | null) =>
    value == null ? "Not scored" : `${Math.round(value * 100)}%`;

  function originality(idea: SolutionPreview): string {
    if (idea.novelty_score != null) return percent(idea.novelty_score);
    if (idea.obviousness_score != null) return percent(1 - idea.obviousness_score);
    return "Not scored";
  }

  function firstText(values?: string[] | null): string | null {
    return values?.find((value) => value.trim())?.trim() ?? null;
  }

  function evidenceAnchor(idea: SolutionPreview): string {
    if (idea.unanchored_hypothesis) return "Hypothesis: no validated pain match";
    return idea.source_pain?.trim()
      || firstText(idea.pain_points_addressed)
      || "No pain source recorded";
  }

  function audience(idea: SolutionPreview): string {
    return idea.source_segment?.trim()
      || firstText(idea.target_personas)
      || "No audience recorded";
  }

  function wedge(idea: SolutionPreview): string {
    return idea.differentiation_locus?.trim()
      || idea.innovation_angle?.trim()
      || firstText(idea.differentiation_factors)
      || idea.value_proposition?.trim()
      || "No wedge recorded";
  }
  function decisionLens(value: SelectionDecisionProfile): string {
    const time = { under_10: "under 10 hrs/week", "10_20": "10-20 hrs/week", "20_40": "20-40 hrs/week", full_time: "full time" }[value.weeklyTime];
    const budget = { under_1k: "under $1k", "1k_5k": "$1k-$5k", "5k_20k": "$5k-$20k", "20k_plus": "$20k+" }[value.budget];
    const team = { solo: "solo", small_team: "small team", funded_team: "funded team" }[value.team];
    const horizon = { "30_days": "revenue in 30 days", "90_days": "revenue in 90 days", "6_months": "revenue in 6 months", patient: "patient horizon" }[value.revenueHorizon];
    return [time, budget, team, horizon].join(" · ");
  }

  function concern(idea: SolutionPreview): string {
    return idea.critic_concern?.trim()
      || idea.incumbent_parity?.trim()
      || idea.data_acquisition_notes?.trim()
      || "No explicit concern recorded";
  }

  type MarketRowKind = "score" | "metric" | "plain" | "evidence" | "concern";
  interface MarketRow {
    label: string;
    kind: MarketRowKind;
    get: (idea: SolutionPreview) => string;
  }

  /** Shared Market-view rows. Order here is the fallback order; differing
   *  rows are surfaced first at render time (orderedMarketRows below). */
  const MARKET_ROWS: MarketRow[] = [
    { label: "Research score", kind: "score", get: (idea) => String(Math.round(computeCompositeScore(idea) * 100)) },
    { label: "Market fit", kind: "metric", get: (idea) => percent(idea.market_fit_score) },
    { label: "Feasibility", kind: "metric", get: (idea) => percent(idea.technical_feasibility_score) },
    { label: "Distribution / SEO", kind: "metric", get: (idea) => percent(idea.seo_scalability_score) },
    { label: "Originality", kind: "metric", get: (idea) => originality(idea) },
    { label: "Build estimate", kind: "plain", get: (idea) => idea.estimated_development_time?.trim() || "Not estimated" },
    { label: "Evidence anchor", kind: "evidence", get: (idea) => evidenceAnchor(idea) },
    { label: "Audience", kind: "plain", get: (idea) => audience(idea) },
    { label: "Distinctive wedge", kind: "plain", get: (idea) => wedge(idea) },
    { label: "Known concern", kind: "concern", get: (idea) => concern(idea) },
  ];

  /** Differences-first ordering: rows where every candidate reads the same
   *  text carry no decision weight, so they sink below the rows that differ.
   *  A single-idea view has nothing to compare, so the fallback order holds. */
  const orderedMarketRows = $derived.by(() => {
    const rows = MARKET_ROWS.map((row) => {
      const values = ideas.map((idea) => row.get(idea));
      const isUniform = ideas.length > 1 && new Set(values).size === 1;
      return { ...row, isUniform };
    });
    return [...rows.filter((row) => !row.isUniform), ...rows.filter((row) => row.isUniform)];
  });

  function variantDialogLabel(): string {
    if (!variantReview) return gc.dialogLabel;
    if (variantReview.operation === "narrow") return "Compare parent and variant";
    if (variantReview.operation === "combine") return "Compare sources and combined variant";
    return "Compare source and variant";
  }

  function variantRegionLabel(): string {
    if (!variantReview) return comparisonContext?.regionLabel ?? "Shortlisted idea comparison";
    if (variantReview.operation === "narrow") return "Parent and variant comparison";
    if (variantReview.operation === "combine") return "Sources and combined variant comparison";
    return "Source and variant comparison";
  }

  function variantIdeaLabel(index: number, revision: number): string {
    if (!variantReview) return `Candidate ${index + 1}`;
    const sourceCount = ideas.length - 1;
    if (index < sourceCount) {
      if (variantReview.operation === "narrow") return `Parent · rev ${revision}`;
      return `${sourceCount > 1 ? `Source ${index + 1}` : "Source"} · rev ${revision}`;
    }
    const label: Record<SynthesisOperation, string> = {
      narrow: "Narrowed variant",
      reposition: "Repositioned variant",
      combine: "Combined variant",
      adjacent: "Adjacent variant",
    };
    return `${label[variantReview.operation]} · rev ${revision}`;
  }

  function ideaKey(idea: SolutionPreview): string {
    return idea.idea_id ?? idea.solution_name;
  }

  function isShortlisted(idea: SolutionPreview): boolean {
    return shortlistedIdeaKeys.includes(ideaKey(idea));
  }

  function useVariant() {
    if (!onUseVariant) return;
    const result = onUseVariant();
    variantActionFailed = !result.ok;
    variantActionMessage = result.message
      ?? (result.ok ? "Variant is now in your shortlist." : "Could not update the shortlist.");
  }

  function trackChallengeRisk(request: SelectionAssumptionPrefill) {
    trackRiskPrefill = request;
    mode = "assumptions";
  }

  function reviewRiskGap(focus: {
    ideaId: string;
    ideaRevision: number;
    lens: SelectionChallengeLens;
    challengeId?: string;
    questionId?: string;
  }) {
    challengeFocus = { requestId: Date.now(), ...focus };
    scopeCandidateId = focus.ideaId;
    mode = "challenge";
  }

  const TAB_LABELS: Record<CockpitMode, string> = {
    market: "Market",
    fit: "Fit for you",
    challenge: "Evidence review",
    risk: "Biggest unknowns",
    assumptions: "Tracked assumptions",
  };

  const helpCopy = $derived(
    tabGroup === "pressure"
      ? "Work left to right when you want a guided path: stress-test the strongest claims, review the decision risks, then turn the important ones into tracked assumptions. Explore freely. The shortlist moves only when you choose an action."
      : "Work left to right when you want a guided path: compare market evidence, then check the options against your constraints. Explore freely. The shortlist moves only when you choose an action.",
  );
</script>

<WorkspaceOverlay {open} size="wide" label={comparisonContext?.dialogLabel ?? variantDialogLabel()} {onClose}>
  <AnnotationSurface
    surfaceKey={cockpitSurfaceKey}
    anchorKey={cockpitSurfaceKey}
    class="decision-cockpit-annotation-surface"
  >
  <article class="cockpit" data-annotation-anchor="selection:comparison">
    <header class="cockpit-head">
      <div>
        <p class="eyebrow">{gc.eyebrow}</p>
        <div class="title-row">
          <h2>{variantReview ? variantDialogLabel() : comparisonContext?.title ?? gc.heading}</h2>
          <DecisionHelp title="Where to start" position="bottom">
            <p>{helpCopy}</p>
          </DecisionHelp>
        </div>
        <p class="intro">
          {#if variantReview}
            The variant was evaluated independently. Source scores, conclusions, and experiment evidence were not copied to it.
          {:else if comparisonContext}
            {comparisonContext.intro}
          {:else}
            {gc.intro}
          {/if}
        </p>
        {#if profile}
          <p class="decision-lens"><strong>Your lens</strong><span>{decisionLens(profile)}</span></p>
        {/if}
      </div>
      <div class="cockpit-head-actions">
        {#if onAskAnalyst}
          <button type="button" class="ask-analyst" onclick={() => onAskAnalyst?.(mode, ideas)}>
            <MessageSquare aria-hidden="true" />{ASK_ANALYST_LABEL}
          </button>
        {/if}
        <button type="button" class="close" aria-label={gc.closeLabel} onclick={onClose}>
          <X class="w-5 h-5" aria-hidden="true" />
        </button>
      </div>
    </header>

    <nav class="cockpit-modes" aria-label="Comparison views">
      <div role="tablist">
      {#each cockpitModes as tabMode (tabMode)}
        <button id={`cockpit-tab-${tabMode}`} type="button" role="tab" aria-selected={mode === tabMode} aria-controls="cockpit-panel" tabindex={mode === tabMode ? 0 : -1} class:is-active={mode === tabMode} onclick={() => selectMode(tabMode)} onkeydown={(event) => handleModeKeydown(event, tabMode)}>{TAB_LABELS[tabMode]}</button>
      {/each}
      </div>
    </nav>

    {#if !variantReview && ideas.length > 0}
      <!-- Scope strip: the one place every view states which candidate(s) it
           reads. Per-candidate views (Evidence check) turn the chips into a
           single-select switcher; all-candidate views keep them passive under
           a mono scope record line. -->
      <div class="scope-strip">
        {#if mode === "challenge"}
          <span class="scope-record" aria-hidden="true">{COCKPIT_SCOPE_LABEL}</span>
          <div class="scope-chips" role="radiogroup" aria-label="Candidate scope">
            {#each ideas as candidate, index (ideaKey(candidate))}
              {@const key = ideaKey(candidate)}
              {@const selected = challengeCandidateId === key}
              <button
                id={`cockpit-scope-${index}`}
                type="button"
                role="radio"
                class="scope-chip scope-chip--switch"
                class:is-selected={selected}
                aria-checked={selected}
                tabindex={selected ? 0 : -1}
                onclick={() => (scopeCandidateId = key)}
                onkeydown={(event) => handleScopeKeydown(event, key)}
              >
                <span class="scope-chip-text">{solutionDisplayTitle(candidate)}</span>
              </button>
            {/each}
          </div>
        {:else}
          <span class="scope-record">{cockpitScopeLine(ideas.length, ideas[0] ? solutionDisplayTitle(ideas[0]) : null)}</span>
          {#if ideas.length > 1}
            <div class="scope-chips">
              {#each ideas as candidate (ideaKey(candidate))}
                <span class="scope-chip"><span class="scope-chip-text">{solutionDisplayTitle(candidate)}</span></span>
              {/each}
            </div>
          {/if}
        {/if}
      </div>
    {/if}

    <div
      class="cockpit-body"
      id="cockpit-panel"
      role="tabpanel"
      aria-labelledby={`cockpit-tab-${mode}`}
      data-annotation-anchor={`selection:decision-cockpit:view:${mode}`}
      tabindex="0"
    >
    {#if mode === "risk"}
      <DecisionRiskQueue {jobId} {ideas} onReviewGap={reviewRiskGap} />
    {/if}

    {#if mode === "assumptions"}
      <AssumptionMap {jobId} {ideas} {onTestUnknown} prefill={trackRiskPrefill ?? assumptionPrefill} />
    {/if}

    {#if mode === "fit"}
      <section class="fit-panel" aria-labelledby="founder-fit-title">
      <header class="fit-head">
        <div>
          <p class="fit-kicker">Fit for you</p>
          <h3 id="founder-fit-title">Challenge the shortlist against your real constraints</h3>
          <p>Independent from the market ranking. Every conclusion cites your profile and the idea fields it used.</p>
        </div>
        <button
          type="button"
          class="fit-action"
          disabled={!profile || !jobId || fitRunning || fitLoading}
          onclick={() => void analyzeFit()}
        >
          {#if fitRunning}<Loader2 class="spin cockpit-spin" aria-hidden="true" /> Analyzing…{:else}{fit ? "Refresh fit" : "Analyze fit for you"}{/if}
        </button>
      </header>

      {#if !profile}
        <div class="fit-empty fit-empty--action">
          <p>Add your build constraints before running this comparison. NicheIQ will not guess your budget, skills, or reach.</p>
          {#if onOpenFounderContext}<button type="button" onclick={onOpenFounderContext}>{founderContextLabel(false)}</button>{/if}
        </div>
      {:else if fitLoading}
        <p class="fit-empty"><Loader2 class="spin cockpit-spin" aria-hidden="true" /> Loading saved guidance…</p>
      {:else if fitError}
        <p class="fit-error" role="alert">{fitError}</p>
      {:else if fit}
        <div class="fit-grid" class:three-ideas={ideas.length === 3}>
          {#each ideas as idea (idea.idea_id ?? idea.solution_name)}
            {@const result = resultFor(idea)}
            {#if result}
              <article class="fit-card" class:is-blocked={result.verdict === "blocked"}>
                <div class="fit-card-top">
                  <span class="fit-verdict fit-verdict--{result.verdict}">{verdictLabel(result.verdict)}</span>
                  <span class="fit-revision">Rev {result.ideaRevision}</span>
                </div>
                <h4>{result.ideaTitle}</h4>
                <p class="fit-summary">{result.summary}</p>
                <dl class="fit-findings">
                  <div><dt>Founder advantage</dt><dd>{result.strongestAdvantage}</dd></div>
                  {#if result.blockingConflict}<div class="fit-blocker"><dt>Blocking conflict</dt><dd>{result.blockingConflict}</dd></div>{/if}
                  <div><dt>Decision-changing unknown</dt><dd>{result.decisionChangingUnknown}</dd></div>
                  <div><dt>Sensitivity</dt><dd>{result.sensitivity}</dd></div>
                </dl>
                <details class="fit-evidence">
                  <summary>Inspect reasoning and source fields</summary>
                  <ul>
                    {#each result.dimensions as dimension (dimension.dimension)}
                      <li>
                        <span class="dimension-status dimension-status--{dimension.status}">{dimension.status}</span>
                        <strong>{dimension.dimension.replaceAll("_", " ")}</strong>
                        <p>{dimension.summary}</p>
                        <code>{dimension.profileFields.map((field) => `profile.${field}`).join(", ")}{dimension.ideaFields.length ? ` · ${dimension.ideaFields.map((field) => `idea.${field}`).join(", ")}` : ""}</code>
                      </li>
                    {/each}
                  </ul>
                </details>
                {#if onTestUnknown}
                  <button type="button" class="test-action" onclick={() => onTestUnknown?.(result.suggestedExperiment)}>
                    <FlaskConical aria-hidden="true" /> {DRAFT_TEST_BRIEF_LABEL}
                  </button>
                {/if}
                {#if result.verdict === "needs_reshape" && jobId && fit && onEvaluateFitReshape}
                  <ReshapeProposalPanel
                    source={{ kind: "founderFit", idea, artifact: fit, result }}
                    {seedCost}
                    disabled={fitRunning || fitLoading}
                    createProposal={() => createFounderFitReshapeProposal(jobId, result.ideaId, result.ideaRevision)}
                    fetchProposal={() => getFounderFitReshapeProposal(jobId, result.ideaId, result.ideaRevision)}
                    onEvaluate={onEvaluateFitReshape}
                    onReview={onReviewFitReshape}
                    onUse={onUseFitReshape}
                  />
                {/if}
              </article>
            {/if}
          {/each}
        </div>
        <p class="fit-provenance">Generated {new Date(fit.createdAt).toLocaleString()} · owner-only</p>
      {:else}
        <p class="fit-empty">{fitStale ? "Your profile or compared idea revisions changed. Run founder fit again for the current shortlist." : "Run the specialist when market evidence alone cannot tell you which idea is practical for you."}</p>
      {/if}
      </section>
    {/if}

    {#if mode === "market"}
      {#if ideas.length > 1}<p class="scroll-hint">Scroll sideways to compare every candidate.</p>{/if}
      <!-- svelte-ignore a11y_no_noninteractive_tabindex -- focus enables keyboard scrolling -->
      <div bind:this={tableScrollEl} class="table-scroll" role="region" tabindex="0" aria-label={variantRegionLabel()}>
        <div
          class="comparison"
          class:single-idea={ideas.length === 1}
          class:three-ideas={ideas.length === 3}
        >
        <div class="corner" aria-hidden="true"></div>
        {#each ideas as idea, index (`${idea.idea_id ?? idea.solution_name}:${index}`)}
          <section class="idea-head" class:has-shortlist-action={Boolean(onToggleShortlist)}>
            <span class="idea-index">{variantIdeaLabel(index, idea.idea_revision ?? 1)}</span>
            <h3>{solutionDisplayTitle(idea)}</h3>
            <p>{idea.short_description?.trim() || idea.description?.trim() || idea.value_proposition}</p>
            {#if onToggleShortlist}
              {@const shortlisted = isShortlisted(idea)}
              <button
                type="button"
                class="idea-shortlist"
                class:is-selected={shortlisted}
                aria-pressed={shortlisted}
                aria-label={`${shortlisted ? "Remove" : "Shortlist"} ${solutionDisplayTitle(idea)}`}
                disabled={shortlistDisabled || (!shortlisted && shortlistAtCapacity)}
                onclick={() => onToggleShortlist?.(idea)}
              >
                {shortlisted ? "Shortlisted" : shortlistAtCapacity ? "Shortlist full" : "Shortlist this"}
              </button>
            {/if}
          </section>
        {/each}
        {#if variantReview}
          <div class="row-label">What changed</div>
          {#each ideas.slice(0, -1) as _}<div class="cell">Source version</div>{/each}
          <div class="cell">{variantReview.changeSummary}</div>

          <div class="row-label">Evidence retained</div>
          {#each ideas.slice(0, -1) as _, index}
            <div class="cell">{variantReview.sourceContributions[index] ?? "Original research basis retained."}</div>
          {/each}
          <div class="cell">Retains the listed source contributions; receives no inherited score.</div>

          <div class="row-label">Must recheck</div>
          {#each ideas.slice(0, -1) as _}<div class="cell">N/A</div>{/each}
          <div class="cell">
            <ul class="recheck-list">
              {#each variantReview.requiresValidation as item}<li>{item}</li>{/each}
            </ul>
          </div>

          <div class="row-label">Experiment origin</div>
          {#each ideas.slice(0, -1) as _, index}
            <div class="cell">
              {variantReview.conclusionOutcome && index === 0
                ? variantReview.conclusionOutcome + " conclusion remains with the source."
                : "The source keeps its prior evidence and conclusions."}
            </div>
          {/each}
          <div class="cell">New candidate. No conclusion transferred.</div>
        {/if}


        {#each orderedMarketRows as row (row.label)}
          <div class="row-label" class:is-uniform={row.isUniform}>{row.label}</div>
          {#each ideas as idea (idea.idea_id ?? idea.solution_name)}
            {#if row.kind === "score"}
              {@const n = row.get(idea)}
              <div class="cell score-cell" aria-label={`${n} out of 100`}>
                <strong aria-hidden="true">{n}</strong><span aria-hidden="true">/100</span>
              </div>
            {:else if row.kind === "metric"}
              <div class="cell metric">{row.get(idea)}</div>
            {:else if row.kind === "evidence"}
              <div class="cell evidence">{row.get(idea)}</div>
            {:else if row.kind === "concern"}
              <div class="cell concern">{row.get(idea)}</div>
            {:else}
              <div class="cell">{row.get(idea)}</div>
            {/if}
          {/each}
        {/each}
        </div>
      </div>
    {:else if mode === "challenge"}
      <EvidenceChallenge
        {jobId}
        {ideas}
        candidateId={challengeCandidateId}
        focus={challengeFocus}
        onTestGap={onTestUnknown}
        onTrackRisk={trackChallengeRisk}
        {onShapeAdjacent}
        {ownerEvidencePrefill}
      />
    {/if}
    </div>

    {#if variantReview}
      <footer class="decision-note variant-decision">
        <div class="decision-copy">
          <strong>Which version earns the next test?</strong>
        </div>
        <div class="decision-actions">
          <button type="button" class="secondary" onclick={onClose}>Keep current shortlist</button>
          {#if onUseVariant}
            <button type="button" onclick={useVariant}>Use variant in shortlist</button>
          {/if}
        </div>
        {#if variantActionMessage}
          <p class:error={variantActionFailed} class="variant-message" role={variantActionFailed ? "alert" : "status"}>{variantActionMessage}</p>
        {/if}
      </footer>
    {/if}
  </article>
  </AnnotationSurface>
</WorkspaceOverlay>

<style>
  /* Height contract: the WorkspaceOverlay frame is viewport-bounded; the
     cockpit fills it and .cockpit-body (or .table-scroll on the Market view)
     owns the scrolling. No own max-height, or the modal chrome and the
     content drift apart. */
  .cockpit {
    display: flex;
    flex-direction: column;
    overflow: hidden;
    background: var(--color-bg-surface);
    color: var(--color-text-primary);
  }
  :global(.decision-cockpit-annotation-surface) {
    --z-annotation-canvas: 1;
    display: flex;
    flex: 1 1 auto;
    width: 100%;
    min-height: 0;
    overflow: hidden;
  }
  :global(.decision-cockpit-annotation-surface) > .cockpit {
    flex: 1 1 auto;
    width: 100%;
    min-height: 0;
  }
  .cockpit-head {
    display: flex;
    flex: 0 0 auto;
    align-items: flex-start;
    justify-content: space-between;
    gap: 2rem;
    padding: 1.2rem 1.5rem 1rem;
    border-bottom: 1px solid var(--color-border);
  }
  .eyebrow {
    margin: 0 0 0.3rem;
    font-family: var(--font-mono);
    font-size: var(--text-11);
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }
  .title-row { display: flex; align-items: center; gap: 0.55rem; }
  .title-row h2 { min-width: 0; }
  h2 {
    max-width: 42ch;
    margin: 0;
    font-size: clamp(1.35rem, 2.25vw, 1.75rem);
    line-height: 1.16;
    text-wrap: balance;
  }
  .intro {
    max-width: 52rem;
    margin: 0.48rem 0 0;
    color: var(--color-text-secondary);
    font-size: var(--text-base);
    line-height: 1.5;
  }
  .decision-lens { display: flex; flex-wrap: wrap; gap: 0.45rem; margin: 0.65rem 0 0; font-size: var(--text-sm); }
  .decision-lens strong { color: var(--color-text-secondary); }
  .decision-lens span {
    font-family: var(--font-mono);
    color: var(--color-text-secondary);
    font-variant-numeric: tabular-nums;
  }
  .cockpit-modes {
    display: flex;
    flex: 0 0 auto;
    gap: 0.2rem;
    min-height: 3.1rem;
    padding: 0 1.5rem;
    border-bottom: 1px solid var(--color-border);
    background: var(--color-bg-surface);
    overflow-x: auto;
    scrollbar-width: none;
  }
  .cockpit-modes::-webkit-scrollbar { display: none; }
  .cockpit-modes > div { display: flex; gap: 0.2rem; min-width: max-content; }
  .cockpit-body {
    display: flex;
    flex-direction: column;
    flex: 1 1 auto;
    min-height: 0;
    overflow-y: auto;
    overscroll-behavior: contain;
    scrollbar-gutter: stable;
  }
  .cockpit-modes button {
    position: relative;
    flex: 0 0 auto;
    min-height: 3.1rem;
    padding: 0.1rem 0.78rem 0;
    border: 0;
    background: transparent;
    color: var(--color-text-muted);
    font: inherit;
    font-size: var(--text-sm);
    font-weight: 700;
    cursor: pointer;
    transition: color 180ms ease, background 180ms ease;
  }
  .cockpit-modes button::after {
    position: absolute;
    right: 0.72rem;
    bottom: -1px;
    left: 0.72rem;
    height: 2px;
    background: transparent;
    content: "";
  }
  .cockpit-modes button:hover { background: var(--color-bg-elevated); color: var(--color-text-primary); }
  .cockpit-modes button:active { background: var(--color-bg-elevated); }
  .cockpit-modes button.is-active {
    color: var(--color-text-primary);
  }
  .cockpit-modes button.is-active::after { background: var(--color-accent); }
  .cockpit-modes button:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: -2px;
  }
  /* ── Scope strip (commit-bar chip recipe; record line for passive scope) ── */
  .scope-strip {
    display: flex;
    flex: 0 0 auto;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem 0.75rem;
    padding: 0.6rem 1.5rem;
    border-bottom: 1px solid var(--color-border);
    background: var(--color-bg-surface);
  }
  .scope-record {
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-11);
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    font-variant-numeric: tabular-nums;
    font-feature-settings: "zero" 0;
    white-space: nowrap;
  }
  .scope-chips {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
    min-width: 0;
  }
  .scope-chip {
    display: inline-flex;
    align-items: center;
    max-width: 14rem;
    min-width: 0;
    padding: 0.25rem 0.5rem;
    border: 1px solid var(--color-border-accent);
    border-radius: var(--radius-md);
    background: var(--color-bg-elevated);
    color: var(--color-text-primary);
    font-size: var(--text-sm);
    font-weight: 600;
    white-space: nowrap;
  }
  .scope-chip-text {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .scope-chip--switch {
    font: inherit;
    font-size: var(--text-sm);
    font-weight: 600;
    border-color: var(--color-border);
    color: var(--color-text-secondary);
    cursor: pointer;
    transition: border-color 120ms ease, background 120ms ease, color 120ms ease;
  }
  .scope-chip--switch:hover {
    border-color: var(--color-border-emphasis);
    color: var(--color-text-primary);
  }
  .scope-chip--switch.is-selected {
    border-color: var(--color-border-accent);
    background: var(--color-accent-subtle);
    color: var(--color-text-primary);
  }
  .scope-chip--switch:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .fit-panel {
    padding: 1.1rem 1.5rem 1.25rem;
    border-bottom: 1px solid var(--color-border-emphasis);
    background: color-mix(in srgb, var(--color-bg-elevated) 78%, var(--color-bg-surface));
  }
  .fit-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1.25rem;
  }
  .fit-kicker {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    margin: 0 0 0.3rem;
    color: var(--color-accent-dark);
    font-family: var(--font-mono);
    font-size: var(--text-11);
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .fit-kicker :global(svg) { width: 0.9rem; height: 0.9rem; }
  .fit-head h3 { margin: 0; font-size: var(--text-lg); line-height: 1.3; }
  .fit-head p:not(.fit-kicker) {
    max-width: 47rem;
    margin: 0.35rem 0 0;
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    line-height: 1.5;
  }
  .fit-action,
  .test-action {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
    min-height: 2.35rem;
    border: 1px solid var(--color-border-emphasis);
    border-radius: 0.6rem;
    font-size: var(--text-13);
    font-weight: 700;
    cursor: pointer;
    transition: transform 180ms ease, border-color 180ms ease, background 180ms ease;
  }
  .fit-action {
    flex: 0 0 auto;
    padding: 0.55rem 0.8rem;
    background: var(--color-text-primary);
    color: var(--color-bg-surface);
  }
  .fit-action:disabled { background: var(--color-bg-hover); color: var(--color-text-muted); cursor: not-allowed; }
  .fit-action:not(:disabled):hover,
  .test-action:hover {
    border-color: color-mix(in srgb, var(--color-accent) 58%, var(--color-border-emphasis));
  }
  .fit-action:focus-visible,
  .test-action:focus-visible,
  .fit-evidence summary:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .fit-action :global(svg), .test-action :global(svg) { width: 0.95rem; height: 0.95rem; }
  :global(.cockpit-spin) { animation: fit-spin 800ms linear infinite; }
  @keyframes fit-spin { to { transform: rotate(360deg); } }
  .fit-empty,
  .fit-error {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    margin: 0.9rem 0 0;
    padding: 0.75rem 0;
    color: var(--color-text-secondary);
    font-size: var(--text-13);
  }
  .fit-empty :global(svg) { width: 1rem; height: 1rem; }
  .fit-empty--action { align-items: center; justify-content: space-between; }
  .fit-empty--action p { margin: 0; }
  .fit-empty--action button {
    flex: 0 0 auto;
    min-height: 2.35rem;
    padding: 0.45rem 0.75rem;
    border: 1px solid var(--color-border-emphasis);
    border-radius: 0.55rem;
    background: var(--color-text-primary);
    color: var(--color-bg-elevated);
    font: inherit;
    font-size: var(--text-sm);
    font-weight: 700;
    cursor: pointer;
  }
  .fit-error { color: var(--color-error-text); }
  .fit-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1rem;
    margin-top: 1rem;
  }
  .fit-grid.three-ideas { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .fit-card {
    display: flex;
    min-width: 0;
    flex-direction: column;
    padding: 0.9rem;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-bg-surface);
  }
  .fit-card.is-blocked { border-color: var(--color-error); }
  .fit-card-top { display: flex; justify-content: space-between; gap: 0.5rem; align-items: center; }
  .fit-verdict,
  .fit-revision,
  .dimension-status {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.035em;
    text-transform: uppercase;
  }
  .fit-verdict { color: var(--color-accent-dark); }
  .fit-verdict--blocked { color: var(--color-error-text); }
  .fit-verdict--insufficient_evidence { color: var(--color-text-muted); }
  .fit-revision { color: var(--color-text-muted); }
  .fit-card h4 { margin: 0.55rem 0 0; font-size: var(--text-base); line-height: 1.32; }
  .fit-summary { margin: 0.4rem 0 0; color: var(--color-text-secondary); font-size: var(--text-13); line-height: 1.48; }
  .fit-findings { display: grid; gap: 0.55rem; margin: 0.8rem 0 0; }
  .fit-findings div { padding-top: 0.5rem; border-top: 1px solid var(--color-border); }
  .fit-findings dt { color: var(--color-text-muted); font-size: var(--text-11); font-weight: 700; }
  .fit-findings dd { margin: 0.18rem 0 0; font-size: var(--text-sm); line-height: 1.44; }
  .fit-findings .fit-blocker dd { color: var(--color-error-text); }
  .fit-evidence { margin-top: 0.75rem; }
  .fit-evidence summary { color: var(--color-text-secondary); font-size: var(--text-sm); font-weight: 700; cursor: pointer; }
  .fit-evidence ul { display: grid; gap: 0.55rem; margin: 0.65rem 0 0; padding: 0; list-style: none; }
  .fit-evidence li { padding-top: 0.5rem; border-top: 1px solid var(--color-border); }
  .fit-evidence li strong { margin-left: 0.35rem; font-size: var(--text-11); text-transform: capitalize; }
  .fit-evidence li p { margin: 0.25rem 0; font-size: var(--text-sm); line-height: 1.42; }
  .fit-evidence code { color: var(--color-text-muted); font-size: var(--text-xs); overflow-wrap: anywhere; }
  .dimension-status--aligned { color: var(--color-success-dark); }
  .dimension-status--conflict { color: var(--color-error-text); }
  .dimension-status--unknown, .dimension-status--irrelevant { color: var(--color-text-muted); }
  .test-action {
    align-self: flex-start;
    margin-top: auto;
    padding: 0.5rem 0.7rem;
    background: var(--color-bg-elevated);
    color: var(--color-text-primary);
  }
  .fit-provenance { margin: 0.75rem 0 0; color: var(--color-text-muted); font-size: var(--text-11); }
  .cockpit-head-actions { display: flex; flex: 0 0 auto; align-items: center; gap: 0.5rem; }
  .ask-analyst {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.38rem;
    min-height: 2.35rem;
    padding: 0.45rem 0.7rem;
    border: 1px solid var(--color-border);
    border-radius: 0.65rem;
    background: var(--color-bg-elevated);
    color: var(--color-text-secondary);
    font: inherit;
    font-size: var(--text-sm);
    font-weight: 700;
    cursor: pointer;
  }
  .ask-analyst :global(svg) { width: 0.85rem; height: 0.85rem; }
  .ask-analyst:hover { border-color: var(--color-accent); color: var(--color-text-primary); }
  .close {
    display: grid;
    place-items: center;
    flex: 0 0 auto;
    width: 2.35rem;
    height: 2.35rem;
    border: 1px solid var(--color-border);
    border-radius: 0.65rem;
    background: var(--color-bg-elevated);
    color: var(--color-text-secondary);
    cursor: pointer;
  }
  .close { transition: transform 180ms ease, border-color 180ms ease, color 180ms ease, background 180ms ease; }
  .close:hover {
    color: var(--color-text-primary);
    border-color: var(--color-border-emphasis);
    background: var(--color-bg-surface);
  }
  .close:active { transform: scale(0.96); }
  .close:focus-visible, .table-scroll:focus-visible, .idea-shortlist:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  /* The Market view's scroll owner for BOTH axes: capped to the panel height
     so the sticky candidate headers actually stick and the horizontal
     scrollbar stays reachable instead of sitting below the fold. */
  .table-scroll { flex: 1 1 auto; min-height: 0; overflow: auto; overscroll-behavior: contain; }
  .scroll-hint { display: none; margin: 0; padding: 0.55rem 1rem; border-bottom: 1px solid var(--color-border); color: var(--color-text-muted); font-size: var(--text-11); }
  .comparison {
    display: grid;
    grid-template-columns: 10rem repeat(2, minmax(15rem, 1fr));
    min-width: 48rem;
    align-items: stretch;
  }
  .comparison.single-idea {
    grid-template-columns: 10rem minmax(20rem, 1fr);
    min-width: 30rem;
  }
  .comparison.three-ideas {
    grid-template-columns: 10rem repeat(3, minmax(15rem, 1fr));
    min-width: 63rem;
  }
  .corner, .idea-head {
    position: sticky;
    top: 0;
    z-index: 2;
    background: var(--color-bg-surface);
    border-bottom: 1px solid var(--color-border-emphasis);
  }
  .corner { left: 0; z-index: 3; }
  .idea-head {
    min-height: 9.5rem;
    padding: 1.1rem 1.2rem;
    border-left: 1px solid var(--color-border);
  }
  .idea-head.has-shortlist-action {
    display: flex;
    min-height: 12rem;
    flex-direction: column;
  }
  .idea-index {
    font-family: var(--font-mono);
    font-size: var(--text-11);
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .idea-head h3 { margin: 0.35rem 0 0.45rem; font-size: var(--text-md); line-height: 1.3; }
  .idea-head p {
    display: -webkit-box;
    overflow: hidden;
    margin: 0;
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    line-height: 1.45;
    line-clamp: 3;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
  }
  .idea-shortlist {
    align-self: flex-start;
    min-height: 2rem;
    margin-top: auto;
    padding: 0.35rem 0.62rem;
    border: 1px solid var(--color-border-emphasis);
    border-radius: 0.5rem;
    background: var(--color-bg-elevated);
    color: var(--color-text-primary);
    font-size: var(--text-sm);
    font-weight: 700;
    cursor: pointer;
    transition: transform 180ms ease, border-color 180ms ease, color 180ms ease, background 180ms ease;
  }
  .idea-shortlist:hover:not(:disabled) {
    border-color: var(--color-accent);
    color: var(--color-accent-dark);
  }
  .idea-shortlist:active:not(:disabled) { transform: scale(0.98); }
  .idea-shortlist.is-selected {
    border-color: color-mix(in srgb, var(--color-accent) 45%, var(--color-border));
    background: color-mix(in srgb, var(--color-accent) 9%, var(--color-bg-elevated));
    color: var(--color-accent-dark);
  }
  .idea-shortlist:disabled {
    opacity: 0.52;
    cursor: not-allowed;
  }
  .row-label, .cell { padding: 0.82rem 1rem; border-bottom: 1px solid var(--color-border); }
  .row-label {
    position: sticky;
    left: 0;
    z-index: 1;
    background: var(--color-bg-elevated);
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    font-weight: 700;
    letter-spacing: 0.025em;
  }
  .row-label.is-uniform {
    color: var(--color-text-muted);
    font-weight: 600;
  }
  .cell {
    border-left: 1px solid var(--color-border);
    color: var(--color-text-primary);
    font-size: var(--text-13);
    line-height: 1.45;
  }
  .recheck-list { margin: 0; padding-left: 1.1rem; }
  .metric { font-family: var(--font-mono); font-size: var(--text-base); font-weight: 700; }
  .score-cell { display: flex; align-items: baseline; gap: 0.2rem; }
  .score-cell strong { font-family: var(--font-mono); font-size: var(--text-2xl); }
  .score-cell span { color: var(--color-text-muted); font-size: var(--text-sm); }
  .evidence { color: var(--color-text-secondary); }
  .concern { color: var(--color-text-primary); }
  .decision-note {
    display: flex;
    flex: 0 0 auto;
    gap: 0.65rem;
    padding: 0.9rem 1.5rem;
    border-top: 1px solid var(--color-border-emphasis);
    background: var(--color-bg-elevated);
    font-size: var(--text-13);
    line-height: 1.45;
  }
  .variant-decision {
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
  }
  .decision-copy {
    display: grid;
    gap: 0.15rem;
  }
  .decision-actions {
    display: flex;
    gap: 0.5rem;
    margin-left: auto;
  }
  .decision-actions button {
    min-height: 2.5rem;
    padding: 0.5rem 0.85rem;
    border: 1px solid var(--color-text-primary);
    border-radius: 0.55rem;
    background: var(--color-text-primary);
    color: var(--color-bg-surface);
    font-size: var(--text-13);
    font-weight: 700;
    transition: transform 120ms ease, background-color 180ms ease;
  }
  .decision-actions button.secondary {
    border-color: var(--color-border-emphasis);
    background: transparent;
    color: var(--color-text-primary);
  }
  .decision-actions button:hover {
    background: color-mix(in srgb, var(--color-text-primary) 88%, var(--color-bg-surface));
  }
  .decision-actions button.secondary:hover {
    background: var(--color-bg-surface);
  }
  .decision-actions button:active {
    transform: translateY(1px) scale(0.98);
  }
  @media (prefers-reduced-motion: reduce) {
    .close:active,
    .idea-shortlist:active:not(:disabled),
    .decision-actions button:active {
      transform: none;
    }
  }
  .decision-actions button:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .variant-message {
    flex-basis: 100%;
    margin: 0;
  }
  .variant-message.error {
    color: var(--color-error-text);
  }

  @media (max-width: 640px) {
    .cockpit-head { padding: 1rem; gap: 1rem; }
    .scope-strip { padding: 0.55rem 1rem; }
    .cockpit-head-actions { align-items: flex-end; flex-direction: column-reverse; }
    .ask-analyst { max-width: 8.5rem; line-height: 1.25; }
    .cockpit-modes { padding-inline: 0.5rem; }
    .cockpit-modes button { min-height: 3rem; padding-inline: 0.65rem; }
    .intro { font-size: var(--text-13); }
    .cockpit-modes { padding-left: 0.55rem; padding-right: 0.55rem; }
    .fit-panel { padding: 1rem; }
    .fit-head { flex-direction: column; }
    .fit-action { width: 100%; }
    .fit-empty--action { align-items: stretch; flex-direction: column; }
    .fit-empty--action button { width: 100%; }
    .fit-grid, .fit-grid.three-ideas { grid-template-columns: 1fr; }
    .scroll-hint { display: block; }
    .comparison.single-idea { grid-template-columns: 7.5rem minmax(0, 1fr); min-width: 0; }
    .decision-note { flex-direction: column; gap: 0.2rem; padding: 0.8rem 1rem; }
    .decision-actions { width: 100%; margin-left: 0; }
    .decision-actions button { flex: 1; }
  }
</style>
