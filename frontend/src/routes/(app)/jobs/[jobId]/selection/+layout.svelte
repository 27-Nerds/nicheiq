<script lang="ts">
  import { page } from "$app/state";
  import { goto, invalidateAll, replaceState } from "$app/navigation";
  import { setContext, type Snippet } from "svelte";
  import type { LayoutData } from "./$types";
  import { MessageSquare } from "lucide-svelte";
  import AnnotationProvider from "$lib/components/annotations/AnnotationProvider.svelte";
  import ChatThread from "$lib/components/chat/ChatThread.svelte";
  import WorkspaceOverlay from "$lib/components/ui/WorkspaceOverlay.svelte";
  import PhaseNav from "$lib/components/nav/PhaseNav.svelte";
  import TourHost from "$lib/tour/TourHost.svelte";
  import TourRestartButton from "$lib/tour/TourRestartButton.svelte";
  import PageHeader from "$lib/components/ui/PageHeader.svelte";
  import { buildSelectionJourney } from "$lib/selection/decisionJourney";
  import ConceptForge from "$lib/components/selection/ConceptForge.svelte";
  import BatchActivity from "$lib/components/selection/BatchActivity.svelte";
  import EvaluationActivity from "$lib/components/selection/EvaluationActivity.svelte";
  import DecisionBrief from "$lib/components/selection/DecisionBrief.svelte";
  import ExperimentWorkspace from "$lib/components/selection/ExperimentWorkspace.svelte";
  import { chatPanel } from "$lib/stores/chatPanel.svelte";
  import { chatLedger } from "$lib/stores/chatLedger.svelte";
  import {
    getStageCosts,
    seedIdea,
    subscribeToProgress,
    shouldKeepSSEOpen,
    ApiError,
    type SelectionWorkspaceContext,
    type IdeaSynthesisPatch,
  } from "$lib/api";
  import type { Job, SolutionPreview } from "$lib/types/job";
  import type { SelectionConceptForgePrefill } from "$lib/types/selectionCopilot";
  import type { SelectionConceptPurpose } from "$lib/types/selectionConceptSet";
  import type {
    SelectionExperimentDraftSeed,
    SelectionExperimentPrefill,
  } from "$lib/types/selectionExperiment";
  import { solutionDisplayTitle } from "$lib/utils/solution-utils";
  import {
    setWorkspaceTools,
    workspaceIdeaKey,
    type WorkspaceChallengeFocus,
    type WorkspaceTestSeed,
  } from "$lib/selection/workspaceTools";
  import {
    WORKSPACE_ROUTES,
    TOOL_NAMES,
    SHORTLIST_TITLE,
    REVIEW_AND_START_LABEL,
    ASK_ANALYST_LABEL,
    CHOOSE_IDEAS_LABEL,
  } from "$lib/selection/labels";
  import {
    SELECTION_LIFECYCLE_CONTEXT,
    type SelectionWorkspaceLifecycle,
  } from "./selectionWorkspace";
  import {
    shouldForceCloseToolsOnStatus,
    shouldRefreshForDraftVersion,
  } from "$lib/selection/workspaceLifecycle";
  import {
    trustedSelectionToolOrigin,
    type SelectionToolOrigin,
  } from "$lib/selection/toolOrigin";
  import {
    currentToolQueryUrl,
    stateAfterToolQueryStrip,
    TOOL_QUERY_KEYS,
    strippedToolSignature,
    toolQuerySignature,
  } from "./toolQuery";
  import { setServedCapThresholds } from "$lib/utils/scoreRationale";

  interface Props {
    data: LayoutData;
    children: Snippet;
  }

  let { data, children }: Props = $props();

  // Inject the backend-served market-fit cap thresholds before any child computes a
  // "capped at X" hint (parent init runs before children, both SSR and client). Values
  // are static per deployment, so a one-time init call is sufficient.
  // svelte-ignore state_referenced_locally -- intentional one-time capture
  setServedCapThresholds(data.metricExplanations?.capThresholds ?? null);

  const MAX_SCOPE = 3;

  const activeSlug = $derived(page.url.pathname.split("/").at(-1) ?? "compare");
  const activeJourneyDestination = $derived(activeSlug);
  let liveStatus = $state<Job["status"] | "">("");
  let shortlistConflict = $state<{
    code: "SELECTION_DRAFT_LOCKED" | "SELECTION_DRAFT_STALE_IDEA" | "SELECTION_DRAFT_CONFLICT";
    message: string;
  } | null>(null);
  let dataRetrying = $state(false);
  let dataRetryError = $state("");
  const currentStatus = $derived(liveStatus || data.job.status);
  const reportAvailable = $derived(
    (data.job.assets ?? []).some((asset) => asset.type === "REPORT_JSON"),
  );
  const decisionStateUnavailable = $derived(data.selectionLoadState.decisionStateUnavailable);
  const interactive = $derived(
    currentStatus === "AWAITING_SELECTION"
    && !decisionStateUnavailable
    && shortlistConflict === null,
  );
  const seedActivities = $derived(
    chatLedger.jobId === data.job.id ? chatLedger.seedActivities : [],
  );
  const synthesisActivities = $derived(
    seedActivities.filter((activity) => activity.kind === "idea_synthesis"),
  );
  const batchActivities = $derived(
    chatLedger.jobId === data.job.id ? chatLedger.batchActivities : [],
  );
  const selectionTransitStatus = $derived(
    ["QUEUED", "RUNNING", "REGENERATING"].includes(currentStatus),
  );
  const seedEvaluationPending = $derived(
    (
      data.job.activeDispatchKind === "SEED_IDEA"
      && ["QUEUED", "RUNNING"].includes(currentStatus)
    )
    || (
      selectionTransitStatus
      && (
        chatLedger.hasPendingSeed
        || chatLedger.activeOperation?.kind === "SEED_IDEA"
      )
    ),
  );
  const batchGenerationPending = $derived(
    (
      data.job.activeDispatchKind === "REGENERATE"
      && ["QUEUED", "REGENERATING"].includes(currentStatus)
    )
    || (
      selectionTransitStatus
      && (
        chatLedger.hasPendingBatch
        || chatLedger.activeOperation?.kind === "REGENERATE"
      )
    ),
  );
  const selectionOperationPending = $derived(seedEvaluationPending || batchGenerationPending);
  /** Pool operations temporarily lock mutations, but comparison remains useful.
   * Terminal research states still retire the workspace. */
  const workspaceReadable = $derived(interactive || selectionOperationPending);
  /** Admin-granted optional decision tools; resolved server-side in +layout.server.ts. */
  const decisionTools = $derived(data.decisionTools === true);
  const lifecycle = $state<SelectionWorkspaceLifecycle>({ status: "", canMutate: false });
  setContext(SELECTION_LIFECYCLE_CONTEXT, lifecycle);
  // QUEUED is ambiguous: a job re-queued AFTER selection is entering Deep
  // Research, but a job that never finished discovery (no stages completed)
  // is just waiting in line — telling that user "Deep Research has started"
  // is wrong twice over.
  const queuedBeforeDiscovery = $derived(
    currentStatus === "QUEUED" && data.job.stagesCompleted === 0,
  );
  const lifecycleMessage = $derived(
    seedEvaluationPending
      ? "The exact direction is being evaluated. Your current candidates and shortlist stay unchanged, and you can keep comparing them."
      : batchGenerationPending
        ? "A new batch is being added. Existing candidate scores and your shortlist stay unchanged; the list may reorder when new candidates arrive."
      : currentStatus === "AWAITING_SELECTION"
      ? ""
      : queuedBeforeDiscovery
        ? "This research is queued. Idea selection opens once discovery produces candidates."
      : ["QUEUED", "RUNNING_PHASE2"].includes(currentStatus)
        ? "Deep Research has started. Idea selection is now locked."
        : currentStatus === "REGENERATING"
          ? "A new batch is being added. Existing candidate scores and your shortlist stay unchanged."
          : currentStatus === "RUNNING"
            ? "Research is running. This saved selection is now read-only."
        : currentStatus === "COMPLETED"
          ? "Deep Research is complete. This saved selection is now read-only."
          : "This research has moved beyond idea selection. The saved scope is now read-only.",
  );
  const selectionLoadWarnings = $derived([
    ...(data.selectionLoadState.decisionStateUnavailable
      ? ["Your saved shortlist and decision state could not be loaded."]
      : []),
    ...(data.selectionLoadState.metricExplanationsUnavailable
      ? ["Score explanations are temporarily unavailable."]
      : []),
    ...(data.selectionLoadState.founderFitUnavailable
      ? ["Saved fit analysis is temporarily unavailable."]
      : []),
    ...(data.selectionLoadState.invalidSolutionCount > 0
      ? [`${data.selectionLoadState.invalidSolutionCount} malformed ${data.selectionLoadState.invalidSolutionCount === 1 ? "candidate was" : "candidates were"} hidden for safety.`]
      : []),
  ]);

  // Sentence-case the niche for display so the H1 matches the hub (finding #10);
  // the stored niche can be lowercase.
  const nicheHeading = $derived(
    data.job.niche ? data.job.niche.charAt(0).toUpperCase() + data.job.niche.slice(1) : data.job.niche,
  );

  // The active tool label drives the breadcrumb tail; the journey drives the
  // sidebar tool statuses — same source the job-page launchpad uses.
  const activeToolLabel = $derived(
    activeSlug === "review"
      ? REVIEW_AND_START_LABEL
      : WORKSPACE_ROUTES.find((route) => route.slug === activeSlug)?.label ?? SHORTLIST_TITLE,
  );
  // Browser-tab title names the active tool (finding #6), not a generic label.
  const tabTool = $derived(
    activeSlug === "compare"
      ? TOOL_NAMES.compare
      : activeSlug === "risks"
        ? TOOL_NAMES.challenge
        : activeSlug === "review"
          ? "Review scope"
          : SHORTLIST_TITLE,
  );
  const journeyTasks = $derived(
    data.decisionState
      ? buildSelectionJourney(data.decisionState, decisionTools).tasks
      : undefined,
  );

  // The job hub is the sole shortlist owner. Routed pages render the saved
  // shortlist or a read-only comparison scope and hand exact proposals back.
  let shortlistKeys = $state<string[]>([]);
  let shortlistVersion = $state(0);
  let hydratedFrom = "";

  $effect(() => {
    const serverItems = data.decisionState?.shortlist.items ?? [];
    const version = data.decisionState?.shortlist.version ?? 0;
    const signature = `${data.job.id}:${version}:${serverItems.map((i) => `${i.ideaId}@${i.ideaRevision}`).join(",")}`;
    if (hydratedFrom === signature) return;
    hydratedFrom = signature;
    shortlistVersion = version;
    shortlistKeys = serverItems
      .map((item) => data.solutions.find((solution) => (
        solution.idea_id === item.ideaId && (solution.idea_revision ?? 1) === item.ideaRevision
      )))
      .filter((solution): solution is SolutionPreview => Boolean(solution))
      .map(workspaceIdeaKey);
  });

  /** Exact revisions resolved from the route drive both content and overlays.
   *  Bare routes are seeded from the saved draft server-side. */
  const activeIdeas = $derived(data.workspace.ideas);
  function workspaceHref(slug: "compare" | "risks" | "review"): string {
    return slug === "review"
      ? `/jobs/${data.job.id}/selection/review`
      : `/jobs/${data.job.id}/selection/${slug}${data.workspace.canonicalQuery}`;
  }

  function workspaceToolHref(
    slug: "compare" | "risks",
    configure: (params: URLSearchParams) => void,
  ): string {
    const params = new URLSearchParams(data.workspace.canonicalQuery.slice(1));
    for (const key of ["tool", "ideaId", "ideaRevision", "assumptionId", "focus"]) {
      params.delete(key);
    }
    configure(params);
    return `/jobs/${data.job.id}/selection/${slug}?${params.toString()}`;
  }

  function proposeIdeas(ideas: SolutionPreview[], reason: "compare_scope" | "branch_result"): void {
    const refs = ideas.flatMap((idea) => idea.idea_id
      ? [{ ideaId: idea.idea_id, ideaRevision: idea.idea_revision ?? 1 }]
      : []);
    if (refs.length < 1 || refs.length > MAX_SCOPE) return;
    void goto(`/jobs/${data.job.id}#opportunities`, {
      state: {
        ...page.state,
        shortlistProposal: {
          requestId: crypto.randomUUID(),
          expectedVersion: shortlistVersion,
          refs,
          returnHref: `${page.url.pathname}${page.url.search}${page.url.hash}`,
          reason,
        },
      },
    });
  }

  function proposeActiveScope(): void {
    proposeIdeas(activeIdeas, "compare_scope");
  }

  function proposeEvaluatedCandidate(
    activity: import("$lib/stores/chatLedger.svelte").SeedActivity,
  ): void {
    const result = activity.result;
    if (!result?.idea_id) return;
    const idea = data.solutions.find((candidate) => (
      candidate.idea_id === result.idea_id
      && (candidate.idea_revision ?? 1) === (result.idea_revision ?? 1)
    ));
    if (idea) proposeIdeas([idea], "branch_result");
  }

  // ── Tools, opened in place over the page that asked for them ──────────────
  let forgeOpen = $state(false);
  let forgePrefill = $state<SelectionConceptForgePrefill | null>(null);
  let forgeOrigin = $state<SelectionToolOrigin | null>(null);
  let forgeError = $state("");
  let testPlannerOpen = $state(false);
  let testPrefill = $state<SelectionExperimentPrefill | null>(null);
  let seedCost = $state<number | null>(null);
  let decisionBriefRef = $state<DecisionBrief | null>(null);
  let toolError = $state("");
  let evaluationPollTimer: ReturnType<typeof setInterval> | null = null;
  let evaluationPollSourceId = $state<string | null>(null);
  /** Set when the automatic poll exhausted its attempts, so the wait can say so and
   *  offer a re-check instead of freezing on a stale "pending". */
  let evaluationStalledSourceId = $state<string | null>(null);
  let batchPollTimer: ReturnType<typeof setInterval> | null = null;
  let batchPollOperationId = $state<string | null>(null);
  let batchPollStalledOperationId = $state<string | null>(null);

  $effect(() => {
    seedCost = data.stageCosts.seed_idea ?? null;
  });

  $effect(() => {
    const jobId = data.job.id;
    // init() already performs the history request and shares its in-flight promise
    // with ChatThread. Chaining reload() here made every workspace navigation fetch
    // the same ledger at least twice before any SSE event occurred.
    void chatLedger.init(jobId);
  });

  function stopEvaluationPoll(): void {
    if (evaluationPollTimer) clearInterval(evaluationPollTimer);
    evaluationPollTimer = null;
    evaluationPollSourceId = null;
  }

  function beginEvaluationPoll(sourceMessageId: string): void {
    if (evaluationPollSourceId === sourceMessageId && evaluationPollTimer) return;
    stopEvaluationPoll();
    evaluationPollSourceId = sourceMessageId;
    evaluationStalledSourceId = null;
    let attempts = 0;
    evaluationPollTimer = setInterval(async () => {
      attempts += 1;
      await chatLedger.reload();
      const outcome = chatLedger.seedOutcome(sourceMessageId);
      if (outcome && outcome !== "pending") {
        stopEvaluationPoll();
        hydratedFrom = "";
        await invalidateAll();
      } else if (attempts >= 200) {
        // Record WHY it stopped. Giving up silently left the pool locked behind a
        // pending flag with no way forward except a manual page reload.
        stopEvaluationPoll();
        evaluationStalledSourceId = sourceMessageId;
      }
    }, 6000);
  }

  function recheckEvaluation(): void {
    const sourceMessageId = evaluationStalledSourceId;
    if (!sourceMessageId) return;
    evaluationStalledSourceId = null;
    beginEvaluationPoll(sourceMessageId);
    void chatLedger.reload();
  }

  function stopBatchPoll(): void {
    if (batchPollTimer) clearInterval(batchPollTimer);
    batchPollTimer = null;
    batchPollOperationId = null;
  }

  function beginBatchPoll(operationId: string): void {
    if (batchPollOperationId === operationId && batchPollTimer) return;
    if (batchPollStalledOperationId === operationId) return;
    stopBatchPoll();
    batchPollOperationId = operationId;
    if (batchPollStalledOperationId !== operationId) batchPollStalledOperationId = null;
    let attempts = 0;
    batchPollTimer = setInterval(async () => {
      attempts += 1;
      await chatLedger.reload();
      const activity = chatLedger.batchActivities.find((item) => item.operationId === operationId);
      if (activity && activity.outcome !== "pending") {
        batchPollStalledOperationId = null;
        stopBatchPoll();
        hydratedFrom = "";
        await invalidateAll();
      } else if (attempts >= 200) {
        stopBatchPoll();
        batchPollStalledOperationId = operationId;
      }
    }, 6000);
  }

  async function recheckBatch(activity: import("$lib/stores/chatLedger.svelte").BatchActivity): Promise<void> {
    const operationId = activity.operationId;
    if (batchPollStalledOperationId !== operationId) return;
    batchPollStalledOperationId = null;
    beginBatchPoll(operationId);
    await chatLedger.reload();
    const refreshed = chatLedger.batchActivities.find((item) => item.operationId === operationId);
    if (refreshed && refreshed.outcome !== "pending") {
      stopBatchPoll();
      hydratedFrom = "";
      await invalidateAll();
    }
  }

  $effect(() => {
    const pending = seedActivities.find((activity) => activity.outcome === "pending");
    if (pending) beginEvaluationPoll(pending.sourceMessageId);
  });
  $effect(() => {
    const pending = batchActivities.find((activity) => activity.outcome === "pending");
    if (pending) beginBatchPoll(pending.operationId);
  });

  $effect(() => () => {
    stopEvaluationPoll();
    stopBatchPoll();
  });

  /** One tool at a time: two stacked aria-modal dialogs corrupt the AX tree. */
  function closeTools(): void {
    forgeOpen = false;
    testPlannerOpen = false;
    testPrefill = null;
    forgePrefill = null;
    forgeOrigin = null;
    forgeError = "";
    toolError = "";
    // A closed tool retires the deep link that opened it — the same ?tool=
    // link must be able to reopen it (P0-E).
    handledToolQuery = "";
    decisionBriefRef?.closeEditor?.();
  }

  let hydratedStatusFrom = "";
  let lastObservedStatus = "";

  $effect(() => {
    const signature = `${data.job.id}:${data.job.status}`;
    if (hydratedStatusFrom === signature) return;
    hydratedStatusFrom = signature;
    liveStatus = data.job.status;
  });

  $effect(() => {
    lifecycle.status = currentStatus;
    lifecycle.canMutate = interactive;
  });

  $effect(() => {
    const jobId = data.job.id;
    if (!shouldKeepSSEOpen(data.job)) return;
    let lastSseStatus = data.job.status;
    // Plain closure variable: dedupes draft broadcasts, never rendered.
    let lastHandledDraftVersion = 0;
    const unsubscribe = subscribeToProgress(
      jobId,
      (job) => {
        // Another tab saved the shortlist: the draft-PUT broadcast carries a
        // newer draft version than ours, so refresh before an edit here 409s.
        // Own saves are excluded — persistShortlist bumps shortlistVersion
        // before this callback can see the broadcast.
        const draftVersion = job?.selectionDraft?.version;
        if (shouldRefreshForDraftVersion(draftVersion, shortlistVersion, lastHandledDraftVersion)) {
          lastHandledDraftVersion = draftVersion!;
          void invalidateAll();
        }
        if (!job?.status || job.status === lastSseStatus) return;
        lastSseStatus = job.status;
        liveStatus = job.status;
        // Operation receipts and status are two halves of the same transition.
        // Reload both so a response-loss admission is still identified as an exact
        // evaluation or additional batch instead of generic queued work.
        void chatLedger.reload();
        void invalidateAll();
      },
      (error) => console.warn("Selection status stream error:", error.message),
    );
    return unsubscribe;
  });

  $effect(() => {
    const status = currentStatus;
    if (!status || lastObservedStatus === status) return;
    lastObservedStatus = status;
    if (status === "AWAITING_SELECTION" || selectionOperationPending) return;
    shortlistConflict = null;
    // REGENERATING is transient (the job returns to AWAITING_SELECTION), so a
    // dirty tool keeps its draft; `interactive` gating disables its submits.
    // Any other flip means selection is over for good — force-close is fine.
    if (!shouldForceCloseToolsOnStatus(status)) return;
    closeTools();
  });

  async function reloadSelectionData(clearConflict = false): Promise<void> {
    if (dataRetrying) return;
    dataRetrying = true;
    dataRetryError = "";
    try {
      hydratedFrom = "";
      await invalidateAll();
      if (clearConflict) shortlistConflict = null;
    } catch (error) {
      dataRetryError = error instanceof Error
        ? error.message
        : "We could not reload the latest selection data.";
    } finally {
      dataRetrying = false;
    }
  }

  function openTestPlanner(seed?: WorkspaceTestSeed): void {
    if (activeIdeas.length === 0) {
      toolError = "Add a candidate to your shortlist before planning a test.";
      return;
    }
    closeTools();
    const requestedIdea = seed
      ? activeIdeas.find((idea) => (
          idea.idea_id === seed.ideaId
          && (idea.idea_revision ?? 1) === seed.ideaRevision
        ))
      : activeIdeas[0];
    if (!requestedIdea?.idea_id) {
      toolError = seed
        ? "That candidate revision is no longer in this research scope. Choose a current idea before planning the test."
        : "Add a candidate to your shortlist before planning a test.";
      return;
    }

    const assumption = seed?.assumptionId
      ? data.decisionState?.assumptions.find((item) => (
          item.id === seed.assumptionId
          && item.idea.ideaId === requestedIdea.idea_id
          && item.idea.ideaRevision === (requestedIdea.idea_revision ?? 1)
        ))
      : undefined;
    const draft: SelectionExperimentDraftSeed = seed?.draft ?? (assumption
      ? {
          ideaId: assumption.idea.ideaId,
          ideaRevision: assumption.idea.ideaRevision,
          assumptionId: assumption.id,
          assumption: assumption.statement,
          whyCritical: assumption.impact,
          originChallengeId: assumption.originChallengeId,
          originQuestionId: assumption.originQuestionId,
        }
      : {
          ideaId: requestedIdea.idea_id,
          ideaRevision: requestedIdea.idea_revision ?? 1,
        });
    testPrefill = { requestId: crypto.randomUUID(), draft };
    testPlannerOpen = true;
  }

  function openCompareView(view: "market" | "founder"): void {
    closeTools();
    void goto(workspaceToolHref("compare", (params) => params.set("view", view)), {
      replaceState: true,
    });
  }

  // ── First-run tutorial ────────────────────────────────────────────────────
  /** One chapter per tool surface; other slugs get none. */
  const tourChapter = $derived(
    activeSlug === "compare" || activeSlug === "risks" || activeSlug === "review"
      ? activeSlug
      : null,
  );
  /** The view the user had before the tour borrowed it, so it can be handed back. */
  let tourPriorView: "market" | "founder" | null = null;

  /**
   * The "Fit for you" step points at `aside.fit-action`, which only exists under
   * `?view=founder` AND with two or more ideas. `.driver-active * { pointer-events: none }`
   * means the tour cannot click the segment control, so the view is switched here.
   * This is a same-route replaceState — the layout is not torn down, nothing is fetched
   * and nothing is charged.
   */
  function prepareTourSurface(): void {
    if (activeSlug !== "compare") return;
    if (data.workspace.ideas.length < 2) return;
    if (data.workspace.compareView === "founder") return;
    tourPriorView = data.workspace.compareView;
    openCompareView("founder");
  }

  function restoreTourSurface(): void {
    if (!tourPriorView) return;
    const view = tourPriorView;
    tourPriorView = null;
    openCompareView(view);
  }

  function evidenceHref(
    focus?: WorkspaceChallengeFocus,
    disclosure?: "proof",
  ): string {
    const params = new URLSearchParams(data.workspace.canonicalQuery.slice(1));
    for (const key of ["tool", "assumptionId", "challengeId", "questionId", "focus"]) {
      params.delete(key);
    }
    if (focus) {
      params.set("ideaId", focus.ideaId);
      params.set("ideaRevision", String(focus.ideaRevision));
      params.set("lens", focus.lens);
    }
    if (disclosure) params.set("focus", disclosure);
    return `/jobs/${data.job.id}/selection/risks?${params.toString()}`;
  }

  function openEvidence(focus?: WorkspaceChallengeFocus, disclosure?: "proof"): void {
    if (activeIdeas.length === 0) {
      toolError = "Add a candidate to your shortlist before checking the evidence.";
      return;
    }
    closeTools();
    void goto(evidenceHref(focus, disclosure), {
      replaceState: true,
      state: page.state,
    });
  }

  function openVariants(
    purpose: SelectionConceptPurpose = data.workspace.alternativeMode,
    origin: SelectionToolOrigin | null = null,
  ): void {
    if (activeIdeas.length === 0) {
      toolError = "Add a candidate to your shortlist before exploring another direction.";
      return;
    }
    if (purpose === "resolve_tradeoff" && activeIdeas.length < 2) {
      toolError = "Choose at least two candidates before resolving a trade-off.";
      return;
    }
    closeTools();
    forgePrefill = {
      requestId: crypto.randomUUID(),
      purpose,
      targetTradeoff: "",
      rationale: "",
      caveats: [],
    };
    forgeOrigin = origin;
    forgeOpen = true;
  }

  function handleForgeClose(): void {
    const currentUrl = currentToolQueryUrl(page.url);
    // The router can expose PageState after the one-shot tool effect has
    // already opened the overlay. Re-read it here instead of relying only on
    // the initial capture, or a job-page launch can be mistaken for an
    // in-place Compare launch.
    const origin = forgeOrigin ?? trustedSelectionToolOrigin(
      page.state.selectionToolOrigin,
      currentUrl.origin,
      data.job.id,
    );
    forgeOpen = false;
    forgePrefill = null;
    forgeOrigin = null;
    forgeError = "";
    handledToolQuery = "";

    if (!origin) return;
    // Clear the consumed return contract on this history entry before leaving.
    // If the owner later uses Forward, Compare must not inherit an old caller.
    replaceState(`${currentUrl.pathname}${currentUrl.search}${currentUrl.hash}`, {
      ...page.state,
      selectionToolOrigin: undefined,
    });
    if (window.history.length > 1) {
      window.history.back();
      return;
    }
    void goto(origin.returnHref, { replaceState: true });
  }

  async function handleForgeEvaluate(
    patch: IdeaSynthesisPatch,
    sourceMessageId: string,
  ): Promise<boolean> {
    forgeError = "";
    try {
      const response = await seedIdea(data.job.id, {
        kind: "idea_synthesis",
        sourceMessageId,
        expectedCost: seedCost ?? 0,
      });
      chatLedger.markSeedPending(sourceMessageId, {
        evaluationId: response.evaluationId ?? response.dispatchId,
        kind: "idea_synthesis",
        proposedTitle: patch.proposedTitle,
      });
      beginEvaluationPoll(sourceMessageId);
      await invalidateAll();
      return true;
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        const fresh = await getStageCosts().catch(() => null);
        seedCost = fresh?.seed_idea ?? seedCost;
        forgeError = "The price changed. Review the new cost and try again.";
      } else {
        forgeError = error instanceof Error ? error.message : "We could not evaluate that direction.";
      }
      return false;
    }
  }

  // ── Deep links ────────────────────────────────────────────────────────────
  // `?tool=` opens a tool on arrival, so the decision rail and the analyst can
  // link straight to a specific check. The param is stripped once handled: it
  // is a one-shot instruction, not overlay state, so closing the tool or
  // refreshing the page never silently re-opens it.
  // Plain variable, not $state: it is a write-only dedupe guard, and reading
  // and writing reactive state in the same effect re-triggers that effect.
  let handledToolQuery = "";
  let handledConceptHandoff = "";

  $effect(() => {
    const prefill = page.state.selectionConceptPrefill;
    if (!prefill || !interactive || !decisionTools || activeSlug !== "compare") return;
    if (handledConceptHandoff === prefill.requestId) return;
    handledConceptHandoff = prefill.requestId;
    const origin = trustedSelectionToolOrigin(
      page.state.selectionToolOrigin,
      page.url.origin,
      data.job.id,
    );

    queueMicrotask(() => {
      openVariants(prefill.purpose, origin);
      forgePrefill = prefill;
      replaceState(`${page.url.pathname}${page.url.search}`, {
        ...page.state,
        selectionConceptPrefill: undefined,
      });
    });
  });

  $effect(() => {
    // `replaceState` shallowly changes the address bar and page.state, but not
    // page.url. Keep the page.url read for navigation reactivity and inspect
    // the live address bar so consuming a tool cannot schedule itself forever.
    const currentUrl = currentToolQueryUrl(page.url);
    const tool = currentUrl.searchParams.get("tool");
    if (!tool || !interactive) return;
    // Every ?tool= value except `compare` opens a decision tool. Without the grant the
    // param is simply retired, so a stale bookmark lands on the page it names instead
    // of opening an overlay whose every request would 403.
    if (!decisionTools && tool !== "compare") {
      queueMicrotask(() => stripToolQuery());
      return;
    }
    const signature = toolQuerySignature(currentUrl);
    if (handledToolQuery === signature) return;
    handledToolQuery = signature;

    const ideaId = currentUrl.searchParams.get("ideaId");
    const ideaRevision = Number(currentUrl.searchParams.get("ideaRevision") ?? "1");
    const requestedLens = currentUrl.searchParams.get("lens");
    const lens = requestedLens === "demand"
      || requestedLens === "distribution"
      || requestedLens === "competition"
      || requestedLens === "dependencies"
      ? requestedLens
      : data.workspace.lens;
    const focus = ideaId && Number.isInteger(ideaRevision) && ideaRevision >= 1
      ? { ideaId, ideaRevision, lens }
      : undefined;
    // Snapshot before stripping: the address bar params are gone by the time
    // the microtask below runs.
    const assumptionId = currentUrl.searchParams.get("assumptionId") ?? undefined;
    const conceptPrefill = page.state.selectionConceptPrefill;
    const toolOrigin = trustedSelectionToolOrigin(
      page.state.selectionToolOrigin,
      currentUrl.origin,
      data.job.id,
    );

    queueMicrotask(() => {
      if (tool === "constraints") decisionBriefRef?.openEditor();
      else if (tool === "fit") {
        // goto() rewrites the URL itself, so stripToolQuery never runs on this
        // path — retire the guard here or the same deep link is dead forever.
        retireToolQuery();
        openCompareView("founder");
        return;
      }
      else if (tool === "compare") {
        retireToolQuery();
        openCompareView("market");
        return;
      }
      else if (tool === "variants") {
        if (activeSlug !== "compare") {
          // The goto target carries ?tool=variants on a DIFFERENT path, so its
          // signature never collides with the retired one.
          retireToolQuery();
          void goto(workspaceToolHref("compare", (params) => {
            params.set("mode", data.workspace.alternativeMode);
            params.set("tool", "variants");
          }), { replaceState: true, state: page.state });
          return;
        }
        // The handoff effect above owns a populated analyst draft. Opening a
        // blank forge here would race it and erase the exact proposed wording.
        if (!conceptPrefill) openVariants(data.workspace.alternativeMode, toolOrigin);
      }
      else if (tool === "assumptions" || tool === "challenge") {
        retireToolQuery();
        openEvidence(focus, tool === "assumptions" ? "proof" : undefined);
        return;
      }
      else if (tool === "tests") {
        const navigationDraft = page.state.selectionTestDraft;
        openTestPlanner(navigationDraft
          ? {
              ideaId: navigationDraft.ideaId,
              ideaRevision: navigationDraft.ideaRevision,
              assumptionId: navigationDraft.assumptionId ?? assumptionId,
              draft: navigationDraft,
            }
          : focus
            ? { ideaId: focus.ideaId, ideaRevision: focus.ideaRevision, assumptionId }
            : undefined);
        stripToolQuery();
        return;
      }

      // Strip AFTER opening: a router that is not ready yet must never stop the
      // tool from opening. `lens` stays; it is real workspace state.
      stripToolQuery();
    });
  });

  /** Re-arms the deep-link guard for the post-strip URL. The guard stores the
   *  handled with-tool signature only for the duration of the open microtask;
   *  a consumed one-shot link must read as new on the next navigation to the
   *  identical URL (P0-E — the guard previously never reset, so a repeat
   *  deep-link neither opened the tool nor stripped the query). */
  function retireToolQuery(): void {
    handledToolQuery = strippedToolSignature(currentToolQueryUrl(page.url));
  }

  /** Drops the one-shot tool params so closing the tool or refreshing never
   *  re-opens something the user already dismissed. On a cold load the router
   *  may not be ready on the first try, so this retries once. */
  function stripToolQuery(attempt = 0): void {
    const stripped = currentToolQueryUrl(page.url);
    const nextState = stateAfterToolQueryStrip(page.state);
    let changed = false;
    for (const key of TOOL_QUERY_KEYS) {
      if (stripped.searchParams.has(key)) {
        stripped.searchParams.delete(key);
        changed = true;
      }
    }
    if (!changed) return;
    // Whether or not replaceState lands on this attempt, the instruction has
    // been consumed — store the post-strip signature so the same deep link can
    // fire again later.
    handledToolQuery = toolQuerySignature(stripped);
    try {
      replaceState(`${stripped.pathname}${stripped.search}`, nextState);
    } catch {
      if (attempt < 1) setTimeout(() => stripToolQuery(attempt + 1), 250);
    }
  }

  // Consumers call these directly; without the grant the openers become no-ops so a
  // component that still holds a reference can't open an overlay that isn't mounted.
  // The shortlist members stay live — they are not decision tools.
  const noop = () => {};
  setWorkspaceTools({
    openChallenge: (focus) => { if (decisionTools) openEvidence(focus); },
    openAssumptions: (focus) => { if (decisionTools) openEvidence(focus, "proof"); },
    openTestPlanner: (...args) => { if (decisionTools) openTestPlanner(...args); },
    openVariants: (...args) => { if (decisionTools) openVariants(...args); },
    openConstraints: () => {
      if (!decisionTools) return noop();
      closeTools();
      decisionBriefRef?.openEditor();
    },
    openFit: () => { if (decisionTools) openCompareView("founder"); },
  });

  // ── Header context and forward action ─────────────────────────────────────
  const profile = $derived(data.decisionState?.profile ?? null);
  const scopeMatchesShortlist = $derived(
    activeIdeas.length === shortlistKeys.length
    && activeIdeas.every((idea) => shortlistKeys.includes(workspaceIdeaKey(idea))),
  );
  const canReviewScope = $derived(
    Boolean(data.decisionState?.deepResearch.eligible)
    && data.workspace.scopeSource !== "preview"
    && scopeMatchesShortlist,
  );
  const reviewScopeHint = $derived(
    canReviewScope
      ? decisionTools
        ? "Risk checks are optional. This scope is ready to review."
        : "This scope is ready to review."
      : activeIdeas.length === 0 || data.workspace.scopeSource === "preview"
        ? "Select at least one idea to review the research scope."
        : !scopeMatchesShortlist
          ? "Save this exact scope before reviewing it."
          : "This shortlist is not ready to review yet.",
  );

  const analystContext = $derived<SelectionWorkspaceContext>({
    workspace: activeSlug === "risks"
      ? "risks"
      : activeSlug === "review"
        ? "candidates"
        : "compare",
    ideas: data.workspace.refs.map((idea) => ({ ...idea })),
    lens: activeSlug === "risks" ? data.workspace.lens : undefined,
  });
  const analystStarters = $derived([
    activeSlug === "compare"
      ? "Explain the most decision-relevant difference between these candidates."
      : activeSlug === "risks"
        ? "Which unresolved evidence gap is most likely to change my choice?"
        : "Help me review the exact ideas and cost before I start Deep Research.",
  ]);
</script>

<svelte:head>
  <title>{tabTool} · {nicheHeading} · NicheIQ</title>
</svelte:head>

<AnnotationProvider
  mode="owner"
  enabled={currentStatus === "AWAITING_SELECTION" || currentStatus === "REGENERATING"}
  showLauncher={false}
  jobId={data.job.id}
  surfaceKey={`selection:workspace:${activeSlug}`}
>
<div class="job-page-shell">
  <PhaseNav
    jobStatus={currentStatus}
    entryMode={data.job.entryMode}
    mode="selection"
    nested
    jobId={data.job.id}
    activeTool={activeJourneyDestination}
    toolTasks={journeyTasks}
    selectedCount={shortlistKeys.length}
    selectionQuery={data.workspace.canonicalQuery}
    availableSectionIds={data.availableSectionIds}
    {decisionTools}
    {reportAvailable}
  />
  <!-- A <div>, not <main>: the (app) layout already renders the page's single
       <main> landmark, and nested mains are invalid. Styling rides the class. -->
  <div class="job-page-content job-page-content--selection">
  <PageHeader
    class="ws-header"
    breadcrumbItems={[
      { label: "Dashboard", href: "/dashboard" },
      { label: SHORTLIST_TITLE, href: `/jobs/${data.job.id}` },
    ]}
    breadcrumbCurrent={activeToolLabel}
    title={nicheHeading}
    titleVariant="research-topic"
  >
    {#snippet actions()}
      <TourRestartButton />
      <button type="button" class="ask-analyst" onclick={() => chatPanel.open()}>
        <MessageSquare aria-hidden="true" />
        {ASK_ANALYST_LABEL}
      </button>
    {/snippet}
  </PageHeader>

  {#if lifecycleMessage}
    <aside class="workspace-state workspace-state--locked" role="status" aria-live="polite">
      <div>
        <strong>
          {seedEvaluationPending
            ? "Evaluating direction"
            : batchGenerationPending
              ? "Adding another batch"
              : "Selection is read-only"}
        </strong>
        <p>{lifecycleMessage}</p>
      </div>
      {#if !selectionOperationPending}
        <a href={currentStatus === "COMPLETED" && reportAvailable
          ? `/jobs/${data.job.id}/report`
          : `/jobs/${data.job.id}`}>
          {currentStatus === "COMPLETED" && reportAvailable ? "Open report" : "View run"}
          <span aria-hidden="true">→</span>
        </a>
      {/if}
    </aside>
  {/if}
  {#if dataRetryError}
    <p class="tool-error" role="alert">{dataRetryError}</p>
  {/if}

  {#if shortlistConflict}
    <aside class="workspace-state workspace-state--conflict" role="alert">
      <div>
        <strong>
          {shortlistConflict.code === "SELECTION_DRAFT_LOCKED"
            ? "Selection was completed elsewhere"
            : "Shortlist needs reconciliation"}
        </strong>
        <p>{shortlistConflict.message}</p>
      </div>
      {#if shortlistConflict.code === "SELECTION_DRAFT_LOCKED"}
        <a href={`/jobs/${data.job.id}`}>View progress <span aria-hidden="true">→</span></a>
      {:else}
        <button type="button" disabled={dataRetrying} onclick={() => void reloadSelectionData(true)}>
          {dataRetrying ? "Loading…" : "Load latest shortlist"}
        </button>
      {/if}
    </aside>
  {/if}

  {#if selectionLoadWarnings.length > 0}
    <aside
      class="workspace-state workspace-state--data"
      role={decisionStateUnavailable ? "alert" : "status"}
      aria-live="polite"
    >
      <div>
        <strong>Some selection data is unavailable</strong>
        {#each selectionLoadWarnings as warning}<p>{warning}</p>{/each}
      </div>
      <button type="button" disabled={dataRetrying} onclick={() => void reloadSelectionData()}>
        {dataRetrying ? "Retrying…" : "Retry"}
      </button>
    </aside>
  {/if}

  <BatchActivity
    activities={batchActivities}
    view="live"
    stalledOperationId={batchPollStalledOperationId}
    onRecheck={recheckBatch}
  />
  <!-- Live state only. A decision tool's own work owns this page; the settled record has
       a single home in the job page's Discovery appendix, reachable from the header tally. -->
  <EvaluationActivity
    jobId={data.job.id}
    activities={seedActivities}
    view="live"
    operation={chatLedger.activeOperation}
    stalled={evaluationStalledSourceId != null}
    onRecheck={recheckEvaluation}
  />
  <EvaluationActivity
    jobId={data.job.id}
    activities={synthesisActivities}
    view="handoff"
    onProposeCandidate={proposeEvaluatedCandidate}
  />

  {#if activeSlug === "compare"}
  <section class="scope-strip" aria-labelledby="scope-title">
    <div class="scope-heading">
      <p id="scope-title">{scopeMatchesShortlist ? "Research shortlist" : "Comparison scope"}</p>
      <span class="scope-count" aria-label={`${activeIdeas.length} of ${MAX_SCOPE} ideas in view`}>
        {activeIdeas.length} <span aria-hidden="true">of {MAX_SCOPE}</span>
      </span>
    </div>
    <div class="candidate-pills">
      {#each activeIdeas as idea (workspaceIdeaKey(idea))}
        {@const shortlisted = shortlistKeys.includes(workspaceIdeaKey(idea))}
        <span class="candidate-pill" class:preview={!shortlisted}>
          <span class="pill-title">{solutionDisplayTitle(idea)}</span>
          <small>{shortlisted ? "Shortlisted" : "Preview only"}</small>
          {#if (idea.idea_revision ?? 1) > 1}
            <small>rev {idea.idea_revision}</small>
          {/if}
        </span>
      {:else}
        <span class="empty-scope">No candidates are available for this research yet.</span>
      {/each}
    </div>
    <div class="scope-actions">
      {#if interactive && !scopeMatchesShortlist && activeIdeas.length > 0}
        <button type="button" class="scope-handoff" onclick={proposeActiveScope}>
          Use this scope
        </button>
      {/if}
      <a href={`/jobs/${data.job.id}#opportunities`}>Edit on Choose ideas</a>
    </div>
    {#if !scopeMatchesShortlist}
      <p class="scope-help">Preview only — your saved shortlist has not changed.</p>
    {/if}
  </section>
  {/if}

  {#if data.workspace.notices.length > 0}
    <aside class="scope-notice" aria-live="polite">
      <span class="notice-icon" aria-hidden="true">i</span>
      <div>
        <strong>We adjusted this link safely</strong>
        {#each data.workspace.notices as notice}<p>{notice}</p>{/each}
        {#if activeIdeas.length === 0}
          <a class="notice-recover" href={`/jobs/${data.job.id}`}>Back to ranked candidates <span aria-hidden="true">→</span></a>
        {/if}
      </div>
    </aside>
  {/if}

  {#if toolError}
    <p class="tool-error" role="alert">{toolError}</p>
  {/if}

  <div
    class="workspace-content"
    aria-disabled={!workspaceReadable}
    inert={!workspaceReadable ? true : undefined}
  >
    {@render children()}
  </div>

  {#if interactive && activeSlug !== "review"}
    <div class="workspace-commit" class:workspace-commit--supporting={activeSlug !== "compare"}>
      <p>
        {reviewScopeHint}
      </p>
      {#if canReviewScope}
        <a class="commit-cta ready" data-tour="workspace-commit" href={workspaceHref("review")}>
          {REVIEW_AND_START_LABEL}<span aria-hidden="true">→</span>
        </a>
      {:else if activeIdeas.length > 0 && !scopeMatchesShortlist}
        <button type="button" class="commit-cta" onclick={proposeActiveScope}>
          Use this scope on Choose ideas<span aria-hidden="true">→</span>
        </button>
      {:else}
        <a class="commit-cta" href={`/jobs/${data.job.id}#opportunities`}>
          {CHOOSE_IDEAS_LABEL}<span aria-hidden="true">→</span>
        </a>
      {/if}
    </div>
  {/if}
  </div>
</div>

<!-- The three decision-tool overlays. Not mounted without the grant: every endpoint
     they call is gated, and `decisionBriefRef` is only ever reached through optional
     chaining, so nothing downstream breaks when it stays undefined. -->
{#if decisionTools}
  <DecisionBrief
    bind:this={decisionBriefRef}
    jobId={data.job.id}
    profile={profile}
    variant="summary"
    hideSummary
    disabled={!interactive}
    onSaved={() => { hydratedFrom = ""; void invalidateAll(); }}
  />

  <ExperimentWorkspace
    open={testPlannerOpen}
    surface="form"
    jobId={data.job.id}
    ideas={activeIdeas}
    prefill={testPrefill}
    seedCost={data.stageCosts.seed_idea ?? null}
    disabled={!interactive}
    onOpenChallenge={() => openEvidence(undefined, "proof")}
    onChanged={() => { void invalidateAll(); }}
    onClose={() => { testPlannerOpen = false; testPrefill = null; handledToolQuery = ""; }}
  />

  <ConceptForge
    open={forgeOpen}
    jobId={data.job.id}
    parents={activeIdeas}
    prefill={forgePrefill}
    initialSets={data.conceptSets}
    {seedCost}
    disabled={!interactive}
    evaluateError={forgeError}
    operation={chatLedger.activeOperation}
    onEvaluate={handleForgeEvaluate}
    onChanged={() => { void invalidateAll(); }}
    onClose={handleForgeClose}
  />
{/if}

<WorkspaceOverlay
  open={chatPanel.isOpen}
  modal={chatPanel.isExpanded}
  label="Analyst conversation"
  onClose={() => chatPanel.close()}
  onEscape={() => (chatPanel.isExpanded ? chatPanel.dock() : chatPanel.close())}
>
  <!-- Esc from the expanded window steps DOWN to docked (onEscape above), not
       out of the conversation; a second Esc closes the docked window. Either
       close survives safely: the composer draft round-trips through chatPanel,
       so the {#if open} unmount can no longer destroy unsent text. -->
  <ChatThread
    jobId={data.job.id}
    dock="rail"
    selectionContext={analystContext}
    starters={analystStarters}
    focused={chatPanel.isExpanded}
    initialDraft={chatPanel.draft(data.job.id)}
    onDraftChange={(text) => chatPanel.setDraft(data.job.id, text)}
    onToggleFocus={() => chatPanel.toggleExpanded()}
    onCollapse={() => chatPanel.close()}
  />
</WorkspaceOverlay>

<!-- First-run tutorial, one chapter per tool surface. Everything these chapters anchor on
     is server-rendered by +layout.server.ts, so there is no client fetch to wait for —
     but the `?tool=` deep-link effect strips its params asynchronously (with a 250ms
     retry), and firing the invitation before that settles would stack it under an
     overlay the link is about to open. -->
{#if tourChapter}
  <TourHost
    chapter={tourChapter}
    enabled={decisionTools}
    ready={!data.selectionLoadState.decisionStateUnavailable
      && data.workspace.ideas.length > 0
      && !TOOL_QUERY_KEYS.some((key) => page.url.searchParams.has(key))}
    suppressed={!interactive}
    deferred={data.workspace.notices.length > 0
      || Boolean(toolError)
      || forgeOpen
      || testPlannerOpen
      || chatPanel.isExpanded}
    onBeforeStart={prepareTourSurface}
    onAfterEnd={restoreTourSurface}
    reflowKey={`${activeSlug}:${data.decisionState?.shortlist.version ?? -1}:${shortlistKeys.join()}`}
  />
{/if}

</AnnotationProvider>

<style>
  /* Same shell as the job page: sidebar + content, full-bleed, matched width.
     The workspace is a drill-down of the decision, not a different app. */
  .job-page-shell { display: flex; width: 100%; min-width: 0; align-items: flex-start; overflow-x: clip; }
  .job-page-content {
    --workspace-ink: var(--color-text-primary);
    --workspace-muted: var(--color-text-secondary);
    --workspace-line: var(--color-border);
    flex: 1;
    min-width: 0;
    box-sizing: border-box;
    width: min(82rem, 100%);
    margin: 0 auto;
    padding: var(--space-8) var(--space-12) var(--space-16);
    color: var(--workspace-ink);
  }

  /* The niche is CONTEXT on a tool page, not the hero — it rides just under the
     breadcrumb, quieter than the tool's own H2. The loudest heading above the
     fold is the tool heading, not the repeated niche name. Scoped via .ws-header
     so the job page's title is untouched. */
  :global(.ws-header .page-header-title--research-topic) { font-size: var(--text-base); line-height: var(--leading-tight); color: var(--color-text-secondary); text-transform: none; }
  :global(.ws-header) { margin-bottom: var(--space-5); }

  /* Breadcrumb must never push past the viewport (clipped at ~768px): give the
     flex chain a real min-width:0 path and ellipsize the current crumb, which
     is the long one (the tool label). */
  :global(.ws-header .page-header-top) { min-width: 0; }
  :global(.ws-header .page-header-top nav) { min-width: 0; max-width: 100%; }
  :global(.ws-header .page-header-top ol) { min-width: 0; max-width: 100%; }
  :global(.ws-header .page-header-top ol li) { min-width: 0; }
  :global(.ws-header .page-header-top ol li:last-child) { overflow: hidden; }
  :global(.ws-header .page-header-top ol li:last-child span) {
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .ask-analyst { display: inline-flex; align-items: center; justify-content: center; gap: var(--space-2); min-height: var(--space-10); padding: var(--space-2) var(--space-3); border: 1px solid var(--color-input-border); border-radius: var(--radius-md); color: var(--workspace-muted); background: transparent; box-shadow: none; font: inherit; font-size: var(--text-13); font-weight: 600; cursor: pointer; transition: border-color var(--duration-normal) var(--ease-default), color var(--duration-normal) var(--ease-default), background var(--duration-normal) var(--ease-default); }
  .ask-analyst:hover { border-color: var(--color-input-border-hover); color: var(--workspace-ink); background: var(--color-bg-surface); }
  .ask-analyst:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  .ask-analyst:active { transform: scale(0.98); }
  .ask-analyst :global(svg) { width: var(--space-4); height: var(--space-4); }

  .scope-strip { display: grid; grid-template-columns: minmax(10rem, auto) minmax(0, 1fr) auto; gap: var(--space-3) var(--space-4); align-items: center; padding: var(--space-3) 0; border-bottom: 1px solid var(--workspace-line); }
  .scope-heading { display: flex; gap: var(--space-1-5); align-items: baseline; }
  .scope-heading > p { margin: 0; color: var(--workspace-muted); font: 700 var(--text-11)/var(--leading-tight) var(--font-mono); letter-spacing: var(--tracking-wider); text-transform: uppercase; }
  .scope-count { color: var(--workspace-ink); font: 700 var(--text-sm)/var(--leading-none) var(--font-mono); font-variant-numeric: tabular-nums; white-space: nowrap; }
  .scope-count span { color: var(--workspace-muted); }
  .candidate-pills { display: grid; grid-template-columns: repeat(2, minmax(12rem, 1fr)); gap: var(--space-2); min-width: 0; align-items: center; }
  .candidate-pill { display: inline-flex; min-width: 0; gap: var(--space-2); align-items: center; padding: var(--space-2) var(--space-2) var(--space-2) var(--space-3); border-radius: var(--radius-md); background: color-mix(in srgb, var(--color-accent) 6%, var(--color-bg-elevated)); box-shadow: inset 0 0 0 1px var(--color-border-accent); }
  .candidate-pill.preview { background: var(--color-bg-surface); box-shadow: inset 0 0 0 1px var(--workspace-line); }
  .pill-title { overflow: hidden; font-size: var(--text-base); font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
  .candidate-pill small { flex: 0 0 auto; color: var(--workspace-muted); font: 600 var(--text-xs)/var(--leading-none) var(--font-mono); }
  .scope-actions { display: flex; flex-wrap: wrap; gap: var(--space-2); align-items: center; justify-content: flex-end; }
  .scope-actions a, .scope-handoff { min-height: var(--space-9); padding: var(--space-2) var(--space-3); border-radius: var(--radius-md); font: inherit; font-size: var(--text-sm); font-weight: 700; text-decoration: none; }
  .scope-actions a { display: inline-flex; align-items: center; color: var(--workspace-muted); }
  .scope-handoff { border: 1px solid var(--color-input-border); color: var(--workspace-ink); background: var(--color-bg-elevated); cursor: pointer; }
  .scope-actions a:hover, .scope-handoff:hover { color: var(--color-accent-dark); background: var(--color-bg-surface); }
  .scope-actions a:focus-visible, .scope-handoff:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  .scope-help { grid-column: 2 / -1; margin: calc(-1 * var(--space-2)) 0 0; color: var(--workspace-muted); font-size: var(--text-sm); }
  .empty-scope { color: var(--workspace-muted); font-size: var(--text-base); }
  .tool-error { margin: var(--space-1-5) 0 0; color: var(--color-error-text); font-size: var(--text-base); }
  .workspace-state {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    gap: var(--space-3) var(--space-6);
    align-items: center;
    margin: var(--space-4) 0;
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--color-border-warning);
    border-radius: var(--radius-lg);
    color: var(--color-warning-dark);
    background: var(--color-warning-subtle);
  }
  .workspace-state--data { border-color: var(--color-border-info); color: var(--color-info-dark); background: var(--color-info-subtle); }
  .workspace-state strong, .workspace-state p { display: block; margin: 0; font-size: var(--text-base); line-height: var(--leading-normal); }
  .workspace-state p + p { margin-top: var(--space-1); }
  .workspace-state a, .workspace-state button {
    display: inline-flex;
    gap: var(--space-2);
    align-items: center;
    min-height: var(--space-10);
    padding: var(--space-2) var(--space-3);
    border: 1px solid currentcolor;
    border-radius: var(--radius-md);
    color: inherit;
    background: transparent;
    font: inherit;
    font-size: var(--text-sm);
    font-weight: 700;
    text-decoration: none;
    cursor: pointer;
  }
  .workspace-state a:hover, .workspace-state button:hover:not(:disabled) { background: color-mix(in srgb, currentcolor 8%, transparent); }
  .workspace-state a:focus-visible, .workspace-state button:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  .workspace-state button:disabled { cursor: wait; color: var(--color-text-muted); background: var(--color-bg-hover); }
  /* Info notice, not an alert: this is a reassuring "we fixed the link" message,
     so it uses INFO tokens (finding #20), matching DecisionStatusBadge non-error. */
  .scope-notice { display: flex; gap: var(--space-3); margin-top: var(--space-4); padding: var(--space-3) var(--space-4); border: 1px solid var(--color-border-info); border-radius: var(--radius-lg); background: var(--color-info-subtle); color: var(--color-info-dark); }
  .notice-icon { display: grid; flex: 0 0 auto; width: var(--space-5); height: var(--space-5); place-items: center; border-radius: var(--radius-full); background: color-mix(in srgb, var(--color-info) 22%, var(--color-bg-elevated)); color: var(--color-info-dark); font-weight: 800; }
  .scope-notice strong, .scope-notice p { display: block; margin: 0; font-size: var(--text-base); line-height: var(--leading-normal); }
  .notice-recover { display: inline-flex; gap: var(--space-1-5); align-items: center; margin-top: var(--space-2); color: var(--color-info-dark); font-size: var(--text-base); font-weight: 700; text-decoration: underline; text-underline-offset: var(--space-1); }
  .notice-recover:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  .workspace-content { min-width: 0; padding: var(--space-8) 0 var(--space-10); }

  /* No page in this workspace ends in a dead end. */
  .workspace-commit { display: flex; flex-wrap: wrap; justify-content: space-between; gap: var(--space-4); align-items: center; margin-bottom: var(--space-12); padding: var(--space-4) var(--space-5); border: 1px solid var(--workspace-line); border-radius: var(--radius-lg); background: var(--color-bg-elevated); }
  .workspace-commit--supporting { padding-inline: 0; border-inline: 0; border-radius: 0; background: transparent; }
  .workspace-commit p { margin: 0; color: var(--workspace-muted); font-size: var(--text-base); }
  .commit-cta { display: inline-flex; gap: var(--space-2); align-items: center; padding: var(--space-2) var(--space-4); border: 1px solid var(--color-input-border); border-radius: var(--radius-md); color: var(--workspace-muted); font-size: var(--text-base); font-weight: 700; text-decoration: none; transition: background var(--duration-fast) var(--ease-default), border-color var(--duration-fast) var(--ease-default), transform var(--duration-fast) var(--ease-default); }
  .commit-cta.ready { border-color: transparent; color: var(--color-text-on-accent); background: var(--color-accent-hover); }
  .workspace-commit--supporting .commit-cta.ready { border-color: var(--color-input-border); color: var(--workspace-ink); background: transparent; }
  .commit-cta:hover { border-color: var(--color-input-border-hover); }
  .commit-cta:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  .commit-cta.ready:hover { background: var(--color-accent-dark); border-color: transparent; }
  .workspace-commit--supporting .commit-cta.ready:hover { border-color: var(--color-border-emphasis); color: var(--workspace-ink); background: var(--color-bg-surface); }
  .commit-cta:active { transform: scale(0.98); }

  :global(.selection-page) { animation: workspace-enter var(--duration-slow) var(--ease-out) both; }
  :global(.selection-page__header) { display: flex; justify-content: space-between; gap: var(--space-8); align-items: end; margin-bottom: var(--space-6); }
  /* Calm section heading: this is the loudest thing above the fold — louder than
     the muted niche label — because the tool is the content, the niche is context. */
  :global(.selection-page h2) { max-width: 30ch; margin: 0; font-family: var(--font-display); font-size: var(--text-4xl); font-weight: 700; line-height: var(--leading-tight); letter-spacing: var(--tracking-tight); text-wrap: balance; }
  :global(.selection-page__lead) { max-width: 68ch; margin: var(--space-2) 0 0; color: var(--workspace-muted); font-size: var(--text-base); line-height: var(--leading-normal); }
  :global(.selection-page__panel) { border: 1px solid var(--workspace-line); border-radius: var(--radius-lg); background: var(--color-bg-elevated); box-shadow: var(--shadow-sm); }
  :global(.selection-page__action) { display: inline-flex; align-items: center; gap: var(--space-2); margin-top: var(--space-4); min-height: var(--space-10); padding: var(--space-2) var(--space-4); border: 0; border-radius: var(--radius-md); color: var(--color-text-on-accent); background: var(--color-accent-hover); font: inherit; font-size: var(--text-base); font-weight: 700; cursor: pointer; transition: background var(--duration-fast) var(--ease-default), transform var(--duration-fast) var(--ease-default); }
  :global(.selection-page__action:hover) { background: var(--color-accent-dark); }
  :global(.selection-page__action:active) { transform: scale(0.98); }
  :global(.selection-page__action:disabled) { cursor: not-allowed; color: var(--color-text-muted); background: var(--color-bg-hover); }
  @keyframes workspace-enter { from { opacity: 0; transform: translateY(var(--space-1-5)); } to { opacity: 1; transform: translateY(0); } }

  @media (max-width: 1279px) {
    /* Same stack as the job page's shell at this breakpoint: below 1280px the
       PhaseNav collapses to its mobile bar, which must sit ABOVE the content
       as a full-width strip, not beside it as a squeezed flex column. */
    .job-page-shell { flex-direction: column; }
    .candidate-pills { grid-template-columns: repeat(2, minmax(12rem, 1fr)); }
  }

  @media (max-width: 767px) {
    .job-page-content { padding: var(--space-5) var(--space-4) var(--space-12); }
    .scope-strip { grid-template-columns: 1fr; align-items: flex-start; }
    .candidate-pills { width: 100%; }
    .candidate-pill { width: 100%; justify-content: space-between; }
    .candidate-pills { grid-template-columns: 1fr; }
    .scope-actions, .scope-help { grid-column: 1; justify-content: flex-start; }
    .scope-actions a, .scope-handoff { min-height: 2.75rem; }
    :global(.selection-page__header) { display: block; }
  }

  @supports not (overflow: clip) {
    .job-page-shell { overflow-x: hidden; }
  }

  :global(body:has([data-form-overlay="true"]) .workspace-overlay:has(.workspace-overlay__frame[aria-label="Analyst conversation"])) {
    visibility: hidden;
    pointer-events: none;
  }

  @media (prefers-reduced-motion: reduce) {
    :global(.selection-page) { animation: none; }
    .ask-analyst, .commit-cta { transition: none; }
    .ask-analyst:active, .commit-cta:active { transform: none; }
    :global(.selection-page__action), :global(.selection-page__action:active) { transition: none; transform: none; }
  }
</style>
