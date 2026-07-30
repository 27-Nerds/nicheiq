<script lang="ts">
  import { goto, pushState, replaceState } from "$app/navigation";
  import { page } from "$app/state";
  import { tick, type Snippet } from "svelte";
  import { SvelteSet } from "svelte/reactivity";
  import {
    Check,
    Plus,
    Loader2,
    ArrowUp,
    ArrowDown,
  } from "lucide-svelte";
  import {
    ASK_ANALYST_LABEL,
    BRANCH_DIRECTION_LABEL,
    CHOOSE_IDEAS_LABEL,
    PRICE_CHANGED_RELOAD,
    PRICE_CHANGED_RETRY,
    RANKED_LIST_HEADING,
    STRESS_TEST_EVIDENCE_LABEL,
    actionBody,
    appendixMetaLine,
    candidateStatsLine,
    generateNewBatchLabel,
  } from "$lib/selection/labels";
  import { overlapWarningText, shortlistOverlaps } from "$lib/selection/overlapWarnings";
  import {
    regenerateIdeas,
    seedIdea,
    getStageCosts,
    saveSelectionDraft,
    getSelectionDecisionState,
    ApiError,
    type IdeaFocus,
    type IdeaSynthesisPatch,
    type NewIdeaSeedPatch,
    type SeedResultSummary,
    type DiscoveryVoteRationale,
    type SelectionCopilotAction,
    type SelectionWorkspaceContext,
  } from "$lib/api";
  import ChatThread from "$lib/components/chat/ChatThread.svelte";
  import { selectionSuggestions } from "$lib/components/chat/suggestions";
  import {
    chatLedger,
    type BatchActivity as BatchActivityRecord,
  } from "$lib/stores/chatLedger.svelte";
  import { chatPanel } from "$lib/stores/chatPanel.svelte";
  import { MessageSquare } from "lucide-svelte";
  import { creditTopUp } from "$lib/stores/creditTopUp.svelte";
  import {
    DEFAULT_STAGE_COSTS,
    type SelectionDecisionProfile,
    type SelectionDraft,
    type SelectionDraftItem,
    type SolutionPreview,
    type StageCosts,
  } from "$lib/types/job";
  import type { SelectionExperimentDraftSeed } from "$lib/types/selectionExperiment";
  import type {
    SelectionDecisionNextAction,
    SelectionDecisionState,
  } from "$lib/types/selectionDecisionState";
  import type { RuledOutFinding, OverlapGroup, MarketReality } from "$lib/types/report";
  import {
    displayCompositeScore,
    solutionDisplayTitle,
    solutionCardDescription,
    solutionStrengthBadge,
    solutionPrimaryStrengthKey,
    validatedBuildComplexity,
    validatedNoveltyLevel,
    fitLabel,
    opportunityShape,
  } from "$lib/utils/solution-utils";
  import { SCORE_DEFINITIONS } from "$lib/utils/scoreDefinitions";
  import {
    adversarialReviewFinding,
    directIncumbentParity,
  } from "$lib/utils/adversarialReview";
  import { humanizeTag, tagDescription } from "$lib/utils/ideaTagLabels";
  import { angleLabel, angleDescription } from "$lib/utils/ideaAngleLabels";
  import {
    buildIdeaReferences,
    matchIdeaReferences,
    type IdeaReference,
  } from "$lib/utils/ideaReferences";
  import Tooltip from "$lib/components/ui/Tooltip.svelte";
  import WorkspaceOverlay from "$lib/components/ui/WorkspaceOverlay.svelte";
  import SolutionDetail from "$lib/components/SolutionDetail.svelte";
  import DecisionBrief from "$lib/components/selection/DecisionBrief.svelte";
  import CollaboratorFeedback from "$lib/components/selection/CollaboratorFeedback.svelte";
  import RuledOutList from "$lib/components/selection/RuledOutList.svelte";
  import ResearchContextNotes from "$lib/components/selection/ResearchContextNotes.svelte";
  import AnalystRecommendation from "$lib/components/selection/AnalystRecommendation.svelte";
  import AnalysisAppendix from "$lib/components/selection/AnalysisAppendix.svelte";
  import IdeaReferenceText from "$lib/components/IdeaReferenceText.svelte";
  import RuledOutDetail from "$lib/components/selection/RuledOutDetail.svelte";
  import FormOverlay from "$lib/components/ui/FormOverlay.svelte";
  import type { SelectionChallengeLens } from "$lib/types/selectionChallenge";
  import type {
    SelectionAssumptionPrefill,
    SelectionConceptForgePrefill,
    SelectionOwnerEvidencePrefill,
  } from "$lib/types/selectionCopilot";
  import DecisionRail from "$lib/components/selection/DecisionRail.svelte";
  import BatchActivity from "$lib/components/selection/BatchActivity.svelte";
  import EvaluationActivity from "$lib/components/selection/EvaluationActivity.svelte";
  import DecisionStatusBadge from "$lib/components/selection/DecisionStatusBadge.svelte";
  import {
    buildSelectionJourney,
    type SelectionJourneyTask,
  } from "$lib/selection/decisionJourney";
  import { createSelectionToolOrigin } from "$lib/selection/toolOrigin";

  const MAX_SELECTIONS = 3;

  interface Props {
    jobId: string;
    solutions: SolutionPreview[];
    creditBalance: number;
    stageCosts?: StageCosts;
    canRegenerate?: boolean;
    ideaBatchCompletedCount?: number | null;
    maxIdeaBatches?: number | null;
    isRegenerating?: boolean;
    selectedSolutions?: string[];
    selectionDraft?: SelectionDraft | null;
    selectedSolutionIds?: string[];
    decisionProfile?: SelectionDecisionProfile | null;
    solutionVotes?: Record<string, number>;
    solutionVotesById?: Record<string, number>;
    voteRationales?: DiscoveryVoteRationale[];
    coverageNotes?: string[] | null;
    examinedRuledOut?: RuledOutFinding[] | null;
    overlapGroups?: OverlapGroup[] | null;
    marketReality?: MarketReality | null;
    ideaPortfolioSummary?: string | null;
    userAdjustments?: string[] | null;
    discussionCount?: number | null;
    painPointCount?: number | null;
    segmentCount?: number | null;
    onComplete?: () => void;
    onRegenerateStart?: () => void;
    /** Durable additional-batch settlement arrived; refresh candidates and preview. */
    onBatchSettled?: () => void;
    /** Emits the decision-journey tasks so the job-page sidebar (PhaseNav) can
     *  render the same two primary decision tools, with the same status, that
     *  the launchpad shows — one status source across the shell. */
    onJourneyTasks?: (tasks: SelectionJourneyTask[] | undefined) => void;
    /** Keeps selection-mode navigation aligned with the unsent local draft. */
    onShortlistChange?: (count: number) => void;
    /** Reports the workbench's current draft VERSION up so the hub page's SSE
     *  drift guard can exclude own saves (mirrors persistShortlist's version bump
     *  in the selection workspace) — fired on hydration and after each save. */
    onShortlistVersionChange?: (version: number) => void;
    /** Fired once a submitted idea seed settles (accepted/demoted/failed/refunded).
     *  SSE's sorted-name diff misses a same-name demotion/score change and can't see
     *  a brand-new ruled-out entry at all — the parent must force BOTH getSolutions()
     *  and getPreviewReport() here rather than rely on the existing SSE reconciliation. */
    onSeedSettled?: (outcome: "accepted" | "demoted" | "failed" | "refunded") => void;
    /** Visitor (read-only) mode: shortlist/Deep-Research affordances are replaced by
     *  the per-row actionSlot (vote button on the shared view). */
    interactive?: boolean;
    /** Admin-granted optional decision tools (build limits, evidence check, questions to
     *  resolve, tests, fit, branch). Fails CLOSED — a caller that doesn't pass it gets
     *  the required path only. The shortlist, ranked table, compare and review are
     *  never affected. */
    decisionTools?: boolean;
    /** Server-authoritative lock for an active pool mutation that may not yet appear in
     * the asynchronously hydrated chat ledger. */
    poolMutationLocked?: boolean;
    totalVotes?: number;
    actionSlot?: Snippet<[{ solution: SolutionPreview; index: number }]>;
  }

  let {
    jobId,
    solutions,
    creditBalance,
    stageCosts = { ...DEFAULT_STAGE_COSTS },
    canRegenerate = false,
    ideaBatchCompletedCount = null,
    maxIdeaBatches = null,
    isRegenerating = false,
    selectedSolutions,
    selectionDraft = null,
    selectedSolutionIds,
    decisionProfile = null,
    solutionVotes = {},
    solutionVotesById = {},
    voteRationales = [],
    coverageNotes = [],
    examinedRuledOut = [],
    overlapGroups = [],
    marketReality = null,
    ideaPortfolioSummary = null,
    userAdjustments = [],
    discussionCount = null,
    painPointCount = null,
    segmentCount = null,
    onRegenerateStart,
    onBatchSettled,
    onJourneyTasks,
    onShortlistChange,
    onShortlistVersionChange,
    onSeedSettled,
    interactive = true,
    decisionTools = false,
    poolMutationLocked = false,
    totalVotes = 0,
    actionSlot,
  }: Props = $props();

  // The generator contract puts the recommendation in the final sentence. Keep that
  // decision separate even when the model returns one long paragraph containing every
  // idea; paragraph-level matching would incorrectly badge every mentioned candidate.
  const summarySections = $derived.by(() => {
    const paragraphs = (ideaPortfolioSummary ?? "")
      .split(/\n\s*\n/)
      .map((paragraph) => paragraph.trim())
      .filter(Boolean);
    if (!paragraphs.length) return { recommendation: "", supportingNotes: [] as string[] };

    const lastParagraph = paragraphs.at(-1) ?? "";
    const sentences = lastParagraph
      .split(/(?<=[.!?])\s+(?=[A-Z0-9])/)
      .map((sentence) => sentence.trim())
      .filter(Boolean);
    const recommendation = sentences.at(-1) ?? lastParagraph;
    const precedingLastParagraph = sentences.slice(0, -1).join(" ");
    const supportingNotes = [
      ...paragraphs.slice(0, -1),
      ...(precedingLastParagraph ? [precedingLastParagraph] : []),
    ];
    return { recommendation, supportingNotes };
  });
  const summaryRecommendation = $derived(summarySections.recommendation);
  const summarySupportingNotes = $derived(summarySections.supportingNotes);
  const summaryParagraphs = $derived(
    summaryRecommendation ? [...summarySupportingNotes, summaryRecommendation] : [],
  );
  // Reference labels carry the DISPLAY title (headline when present): analyst
  // prose cites internal codenames, but the rendered link should not.
  const ideaReferences = $derived.by(() => {
    const ruledOut = examinedRuledOut ?? [];
    return buildIdeaReferences(solutions, ruledOut).map((reference) => {
      if (reference.kind === "ranked") {
        const match = solutions.find((candidate) => candidate.solution_name === reference.solutionName);
        return match ? { ...reference, label: solutionDisplayTitle(match) } : reference;
      }
      const headline = (reference.ruledOutIndex != null
        ? ruledOut[reference.ruledOutIndex]?.idea?.headline
        : null)?.trim();
      return headline ? { ...reference, label: headline } : reference;
    });
  });
  const hasExplicitRecommendation = $derived(
    /\b(?:recommend(?:ed|s|ing)?|most deserves?|strongest|best (?:idea|option|candidate|pick)|top (?:idea|option|candidate|pick)|prioriti[sz]e|validate(?:d|s|ing)? first|first choice)\b/i
      .test(summaryRecommendation),
  );
  const analystPickNames = $derived(new Set(
    hasExplicitRecommendation
      ? matchIdeaReferences(summaryRecommendation, ideaReferences)
          .flatMap((segment) => (
            segment.reference?.kind === "ranked" && segment.reference.solutionName
              ? [segment.reference.solutionName]
              : []
          ))
      : [],
  ));

  // ── Selection state ──
  let selectedIdeaKeys = new SvelteSet<string>();
  let copilotShortlistReview = $state<{
    requestId: string;
    expectedVersion: number;
    ideas: SolutionPreview[];
    rationale: string;
    source: "analyst" | "comparison";
  } | null>(null);
  let copilotShortlistError = $state("");
  let activeDecisionProfile = $state<SelectionDecisionProfile | null>(null);
  let decisionProfileSyncJobId = $state("");
  let pendingDecisionProfileKey = $state<string | null>(null);
  let staleDecisionProfileKey = $state<string | null>(null);
  let selectLoading = $state(false);
  let selectError = $state("");
  let modalIndex = $state<number | null>(null); // index into the current ranked pool
  let detailTab = $state<"overview" | "detail">("overview");
  let detailUrlError = $state("");
  let detailHistoryOwned = false;
  let handledDetailQuery = "";
  let ruledOutDetail = $state<RuledOutFinding | null>(null);
  let returnToChatState = $state<"docked" | "expanded" | null>(null);
  type ShortlistSaveState = "idle" | "saving" | "saved" | "error";
  let shortlistSaveState = $state<ShortlistSaveState>("idle");
  let shortlistSaveError = $state("");
  let shortlistSaveConflict = $state(false);
  let shortlistDraftVersion = $state(0);
  let shortlistHydrationKey = $state<string | null>(null);
  let shortlistSaveQueued = false;
  let shortlistSaveRunning = $state(false);
  let analystStarterPrompt = $state<string | null>(null);
  let selectionDecisionState = $state<SelectionDecisionState | null>(null);
  let selectionDecisionStateLoading = $state(false);
  let selectionDecisionStateError = $state("");
  let selectionDecisionStateRequest = 0;
  let handledSelectionToolQuery = "";
  let handledShortlistProposal = "";

  function ideaKey(solution: SolutionPreview): string {
    return solution.idea_id
      ? `${solution.idea_id}:${solution.idea_revision ?? 1}`
      : `legacy:${solution.solution_name}`;
  }

  $effect(() => {
    const proposal = page.state.shortlistProposal;
    if (!interactive || !proposal || proposal.requestId === handledShortlistProposal) return;
    handledShortlistProposal = proposal.requestId;
    const proposedIdeas = proposal.refs.flatMap((reference) => {
      const idea = solutions.find((candidate) => (
        candidate.idea_id === reference.ideaId
        && (candidate.idea_revision ?? 1) === reference.ideaRevision
      ));
      return idea ? [idea] : [];
    });

    replaceState(`${page.url.pathname}${page.url.search}${page.url.hash}`, {
      ...page.state,
      shortlistProposal: undefined,
    });

    if (
      proposedIdeas.length !== proposal.refs.length
      || proposedIdeas.length < 1
      || proposedIdeas.length > MAX_SELECTIONS
    ) {
      selectError = "One or more proposed candidate revisions are no longer available. Your shortlist was not changed.";
      return;
    }

    closeAllOverlays();
    copilotShortlistReview = {
      requestId: proposal.requestId,
      expectedVersion: proposal.expectedVersion,
      ideas: proposedIdeas,
      source: "comparison",
      rationale: proposal.reason === "branch_result"
        ? "Review the evaluated direction before adding it to Deep Research."
        : "This exact comparison scope was handed back for shortlist review.",
    };
    copilotShortlistError = proposal.expectedVersion === shortlistDraftVersion
      ? ""
      : "Your shortlist changed after this scope was prepared. Keep the current shortlist and reopen Compare before applying it.";
  });

  function solutionForKey(key: string): SolutionPreview | undefined {
    return solutions.find((solution) => ideaKey(solution) === key);
  }
  function shortlistDraftItems(): SelectionDraftItem[] | null {
    const items: SelectionDraftItem[] = [];
    for (const key of selectedIdeaKeys) {
      const solution = solutionForKey(key);
      if (!solution?.idea_id) return null;
      items.push({
        ideaId: solution.idea_id,
        ideaRevision: solution.idea_revision ?? 1,
      });
    }
    return items;
  }

  async function loadSelectionDecisionState(): Promise<void> {
    if (!interactive || !jobId) return;
    const request = ++selectionDecisionStateRequest;
    selectionDecisionStateLoading = true;
    selectionDecisionStateError = "";
    try {
      const state = await getSelectionDecisionState(jobId);
      if (request !== selectionDecisionStateRequest || state.jobId !== jobId) return;
      selectionDecisionState = state;
    } catch (error) {
      if (request !== selectionDecisionStateRequest) return;
      selectionDecisionStateError = error instanceof Error
        ? error.message
        : "We couldn't update the suggested next step.";
    } finally {
      if (request === selectionDecisionStateRequest) selectionDecisionStateLoading = false;
    }
  }

  async function flushShortlistSaves(): Promise<void> {
    if (shortlistSaveRunning) return;
    shortlistSaveRunning = true;
    try {
      while (shortlistSaveQueued) {
        shortlistSaveQueued = false;
        const items = shortlistDraftItems();
        if (!items) {
          shortlistSaveState = "error";
          shortlistSaveError = "This shortlist contains an idea without a stable identity. Refresh and try again.";
          break;
        }
        try {
          const saved = await saveSelectionDraft(jobId, shortlistDraftVersion, items);
          shortlistDraftVersion = saved.version;
          onShortlistVersionChange?.(saved.version);
          shortlistSaveState = shortlistSaveQueued ? "saving" : "saved";
          shortlistSaveError = "";
          shortlistSaveConflict = false;
          void loadSelectionDecisionState();
        } catch (error) {
          shortlistSaveQueued = false;
          shortlistSaveState = "error";
          shortlistSaveConflict = error instanceof ApiError && error.status === 409;
          shortlistSaveError = error instanceof Error
            ? error.message
            : "We couldn't save your shortlist. Try again.";
          break;
        }
      }
    } finally {
      shortlistSaveRunning = false;
    }
  }

  function queueShortlistSave(): void {
    if (!interactive || !jobId) return;
    shortlistSaveQueued = true;
    shortlistSaveState = "saving";
    shortlistSaveError = "";
    shortlistSaveConflict = false;
    void flushShortlistSaves();
  }

  function retryShortlistSave(): void {
    queueShortlistSave();
  }

  function reloadShortlist(): void {
    window.location.reload();
  }


  interface CollaboratorFeedbackGroup {
    key: string;
    linked: boolean;
    solutionName: string;
    comments: string[];
  }

  const collaboratorFeedbackGroups = $derived.by(() => {
    const nameCounts = new Map<string, number>();
    for (const solution of solutions) {
      nameCounts.set(solution.solution_name, (nameCounts.get(solution.solution_name) ?? 0) + 1);
    }

    const groups = new Map<string, CollaboratorFeedbackGroup>();
    for (const rationale of voteRationales) {
      const solution = rationale.solutionId
        ? solutions.find((candidate) => candidate.idea_id === rationale.solutionId) ?? null
        : nameCounts.get(rationale.solutionName) === 1
          ? solutions.find((candidate) => candidate.solution_name === rationale.solutionName) ?? null
          : null;
      const key = solution
        ? ideaKey(solution)
        : rationale.solutionId
          ? `previous:${rationale.solutionId}`
          : `legacy:${rationale.solutionName}`;
      const existing = groups.get(key);
      if (existing) {
        existing.comments.push(rationale.comment);
      } else {
        groups.set(key, {
          key,
          linked: solution !== null,
          solutionName: solution ? solutionDisplayTitle(solution) : rationale.solutionName,
          comments: [rationale.comment],
        });
      }
    }

    return [...groups.values()].sort((a, b) => {
      if (a.linked && !b.linked) return -1;
      if (!a.linked && b.linked) return 1;
      return a.solutionName.localeCompare(b.solutionName);
    });
  });
  const collaboratorRationaleCount = $derived(
    collaboratorFeedbackGroups.reduce((total, group) => total + group.comments.length, 0),
  );

  function voteCountFor(solution: SolutionPreview): number {
    return solution.idea_id && solutionVotesById[solution.idea_id] !== undefined
      ? solutionVotesById[solution.idea_id]
      : solutionVotes[solution.solution_name] ?? 0;
  }

  // Restore the owner-only working shortlist once. An empty draft is authoritative;
  // the legacy final-selection fields are only a compatibility fallback.
  $effect(() => {
    const poolKey = solutions
      .map(solution => `${solution.idea_id ?? solution.solution_name}:${solution.idea_revision ?? 1}`)
      .join("|");
    const hydrationKey = `${jobId}:${selectionDraft?.version ?? "legacy"}:${poolKey}`;
    if (shortlistHydrationKey === hydrationKey) return;
    selectedIdeaKeys.clear();
    if (selectionDraft) {
      for (const item of selectionDraft.items) {
        const solution = solutions.find(
          candidate => candidate.idea_id === item.ideaId
            && (candidate.idea_revision ?? 1) === item.ideaRevision,
        );
        if (solution) selectedIdeaKeys.add(ideaKey(solution));
      }
    } else {
      const storedKeys = selectedSolutionIds?.length ? selectedSolutionIds : selectedSolutions;
      for (const storedKey of storedKeys ?? []) {
        const solution = solutions.find(
          item => ideaKey(item) === storedKey
            || item.idea_id === storedKey
            || item.solution_name === storedKey,
        );
        if (solution) selectedIdeaKeys.add(ideaKey(solution));
      }
    }
    shortlistDraftVersion = selectionDraft?.version ?? 0;
    onShortlistVersionChange?.(shortlistDraftVersion);
    shortlistSaveState = selectionDraft ? "saved" : "idle";
    shortlistSaveError = "";
    shortlistSaveConflict = false;
    shortlistHydrationKey = hydrationKey;
  });

  $effect(() => {
    const identityKey = solutions
      .map(solution => `${solution.idea_id ?? solution.solution_name}:${solution.idea_revision ?? 1}`)
      .join("|");
    if (!interactive || !jobId || !identityKey) return;
    void loadSelectionDecisionState();
  });

  function decisionProfileKey(profile: SelectionDecisionProfile | null): string {
    return profile ? JSON.stringify(profile) : "null";
  }

  $effect(() => {
    const incomingKey = decisionProfileKey(decisionProfile);
    if (decisionProfileSyncJobId !== jobId) {
      decisionProfileSyncJobId = jobId;
      pendingDecisionProfileKey = null;
      staleDecisionProfileKey = null;
      activeDecisionProfile = decisionProfile;
      return;
    }
    if (pendingDecisionProfileKey !== null) {
      if (incomingKey === staleDecisionProfileKey) return;
      pendingDecisionProfileKey = null;
      staleDecisionProfileKey = null;
    }
    activeDecisionProfile = decisionProfile;
  });

  function handleDecisionProfileSaved(profile: SelectionDecisionProfile): void {
    staleDecisionProfileKey = decisionProfileKey(decisionProfile);
    pendingDecisionProfileKey = decisionProfileKey(profile);
    activeDecisionProfile = profile;
    void loadSelectionDecisionState();
  }

  // Handle on the embedded ChatThread — lets a regenerate/confirm-selection
  // action cancel an in-flight chat stream first, so ChatThread's own local
  // `messages` state can't mutate after the parent has already moved on.
  let chatThreadRef: ChatThread | undefined = $state();
  let decisionBriefRef: DecisionBrief | undefined = $state();
  // Weak-pool starter chip (2026-07-12) — ChatThread learns this from the chat-history
  // response (GET /:jobId/chat/history's `weakPool` flag) and reports it back via
  // bind:weakPool, so this doesn't need its own second history fetch.
  let weakPool = $state(false);

  // ── Focus management for the analyst window ──
  // Opening/closing swaps the launcher and the window in the DOM, which destroys
  // whichever element the keyboard user was standing on. Without this, activating
  // the launcher dumped focus to <body>, and closing did the same in reverse.
  let launcherEl: HTMLButtonElement | undefined = $state();
  let restoreFocusToLauncher = $state(false);

  $effect(() => {
    if (chatPanel.isOpen || !restoreFocusToLauncher || !launcherEl) return;
    launcherEl.focus();
    restoreFocusToLauncher = false;
  });

  function closeChatOverlay() {
    if (chatPanel.isExpanded) {
      chatPanel.dock();
    } else {
      restoreFocusToLauncher = true;
      chatPanel.close();
    }
  }

  function askAnalystAboutCollaboratorFeedback() {
    analystStarterPrompt =
      "Summarize the anonymous collaborator feedback by idea. Identify agreements, disagreements, and useful changes, but treat every note as unverified preference input rather than market evidence or validation.";
    chatPanel.open();
  }

  function askAnalystAboutDecisionStep(action: SelectionDecisionNextAction) {
    const ideaContext = action.ideas.length > 0
      ? action.ideas.map((idea) => '"' + idea.title + '" (revision ' + idea.ideaRevision + ')').join(" and ")
      : "my current shortlist";
    const lensContext = action.lens ? ` Focus on the ${action.lens.toLowerCase()} evidence lens.` : "";
    analystStarterPrompt =
      `Help me with the suggested selection step for ${ideaContext}: ${actionBody(action)}${lensContext} `
      + "Answer in plain prose. Only prepare a draft form if I explicitly ask you to, and never save, submit, launch, pay for, or shortlist anything.";
    chatPanel.open();
  }

  // ── Regeneration state ──
  let regenerating = $state(false);
  let regenerateError = $state("");
  let regenerateOverlayOpen = $state(false);
  let batchPollTimer: ReturnType<typeof setInterval> | null = null;
  /** Plain `let`, never `$state`: both are read by the $effect that also drives them,
   *  so as reactive state they would re-trigger the very effect they exist to dedupe. */
  let batchPollOperationId: string | null = null;
  const abandonedBatchPolls = new Set<string>();
  let batchPollStalledOperationId = $state<string | null>(null);
  let regenerateClientRequestId = $state(crypto.randomUUID());
  let regenerateCostOverride = $state<number | null>(null);
  const regenerateCost = $derived(
    regenerateCostOverride ?? stageCosts.regenerate_ideas,
  );
  const canAffordRegenerate = $derived(
    creditBalance >= regenerateCost,
  );
  const completedBatchCount = $derived(
    typeof ideaBatchCompletedCount === "number" ? ideaBatchCompletedCount : 0,
  );
  const batchMaximum = $derived(
    typeof maxIdeaBatches === "number" ? maxIdeaBatches : 0,
  );
  const batchUsageKnown = $derived(
    typeof ideaBatchCompletedCount === "number"
    && Number.isInteger(ideaBatchCompletedCount)
    && typeof maxIdeaBatches === "number"
    && Number.isInteger(maxIdeaBatches)
    && batchMaximum > 0,
  );
  const batchLimitReached = $derived(
    batchUsageKnown && completedBatchCount >= batchMaximum,
  );
  const canRequestBatch = $derived(
    canRegenerate && !batchLimitReached,
  );
  const REGEN_FOCUSES = [
    { value: "auto", label: "Auto" },
    { value: "novelty", label: "Differentiation" },
    { value: "distribution", label: "Distribution" },
  ] as const;
  let regenerateFocus = $state<"auto" | "novelty" | "distribution">("auto");
  $effect(() => {
    if (!isRegenerating && regenerating) regenerating = false;
  });

  function stopBatchPoll() {
    if (batchPollTimer) clearInterval(batchPollTimer);
    batchPollTimer = null;
    batchPollOperationId = null;
  }

  function beginBatchPoll(operationId: string) {
    // Each tick's chatLedger.reload() reassigns the batch-activity map, which re-runs the
    // $effect that calls us. Without these guards the interval would be torn down and
    // rebuilt every tick — resetting `attempts`, so the give-up cap could never fire, and
    // restarting a poll we had already abandoned.
    if (batchPollOperationId === operationId || abandonedBatchPolls.has(operationId)) return;
    stopBatchPoll();
    batchPollOperationId = operationId;
    if (batchPollStalledOperationId !== operationId) batchPollStalledOperationId = null;
    let attempts = 0;
    batchPollTimer = setInterval(async () => {
      attempts += 1;
      await chatLedger.reload();
      const activity = chatLedger.batchActivities.find((item) => item.operationId === operationId);
      if (activity && activity.outcome !== "pending") {
        abandonedBatchPolls.delete(operationId);
        batchPollStalledOperationId = null;
        stopBatchPoll();
        onBatchSettled?.();
      } else if (attempts >= 200) {
        abandonedBatchPolls.add(operationId);
        stopBatchPoll();
        batchPollStalledOperationId = operationId;
      }
    }, 6000);
  }

  async function recheckBatch(activity: BatchActivityRecord) {
    const operationId = activity.operationId;
    if (batchPollStalledOperationId !== operationId) return;
    abandonedBatchPolls.delete(operationId);
    batchPollStalledOperationId = null;
    beginBatchPoll(operationId);
    await chatLedger.reload();
    const refreshed = chatLedger.batchActivities.find((item) => item.operationId === operationId);
    if (refreshed && refreshed.outcome !== "pending") {
      stopBatchPoll();
      onBatchSettled?.();
    }
  }

  $effect(() => () => stopBatchPoll());

  // `focusOverride` lets the chat patch card ("Apply changes") drive the same
  // call the manual focus buttons use, instead of duplicating the credit/402
  // handling in ChatThread — the tool only ever proposes a change; this is the
  // one place it's actually applied (regenerate-ideas route, unchanged).
  async function handleRegenerate(focusOverride?: IdeaFocus) {
    if (
      !canRequestBatch
      || regenerating
      || isRegenerating
      || seedPending
      || chatLedger.hasPendingSeed
      || chatLedger.activeOperation?.kind === "SEED_IDEA"
    ) return;
    const focus = focusOverride ?? regenerateFocus;
    regenerateFocus = focus;
    regenerating = true;
    regenerateError = "";
    chatThreadRef?.stopStreaming();
    try {
      const response = await regenerateIdeas(
        jobId,
        {
          clientRequestId: regenerateClientRequestId,
          expectedCost: regenerateCost,
          idea_focus: focus,
        },
      );
      regenerateClientRequestId = crypto.randomUUID();
      chatLedger.markBatchPending(response.operationId, {
        ordinal: response.batchOrdinal,
        focus: response.focus ?? focus,
      });
      beginBatchPoll(response.operationId);
      regenerateOverlayOpen = false;
      onRegenerateStart?.();
    } catch (e) {
      if (e instanceof ApiError && e.status === 402) {
        creditTopUp.show({
          balance: creditBalance,
          required: regenerateCost,
          stageName: "idea regeneration",
        });
      } else if (
        e instanceof ApiError
        && e.status === 409
        && (e.details as { code?: string } | undefined)?.code === "PRICE_CHANGED"
      ) {
        try {
          const fresh = await getStageCosts();
          regenerateCostOverride = fresh.regenerate_ideas;
          regenerateError = PRICE_CHANGED_RETRY;
        } catch {
          regenerateError = PRICE_CHANGED_RELOAD;
        }
      } else {
        regenerateError =
          e instanceof Error ? e.message : "Failed to generate ideas";
      }
      regenerating = false;
    }
  }

  async function handleApplyPatch(ideaFocus: IdeaFocus) {
    await handleRegenerate(ideaFocus);
  }

  // ── Idea seed (chat-composed idea evaluation) ──
  //
  // Same purchase idiom as gate Continue: the price shown is the price charged,
  // required (not optional) — the server 409s (PRICE_CHANGED) rather than silently
  // charging a different number if `seed_idea` was re-priced mid-session.
  let seedPending = $state(false);
  let seedError = $state("");
  let seedCostOverride = $state<number | null>(null);
  const seedCost = $derived(seedCostOverride ?? stageCosts.seed_idea ?? null);
  let seedPollTimer: ReturnType<typeof setInterval> | null = null;
  /** Set when the seed poll exhausted its attempts, so the wait can offer a re-check. */
  let seedPollStalledId = $state<string | null>(null);
  let seedHighlightName = $state<string | null>(null);
  let batchHighlightIdeaIds = $state<Set<string>>(new Set());
  let seedHighlightRuledOutIndex = $state<number | null>(null);
  let seedBanner = $state<{ outcome: "accepted" | "demoted" | "failed" | "refunded" } | null>(null);

  // One paid pool-mutation operation at a time (mirrors the backend's single
  // `Job.activeDispatchId`) — gates the seed card, regenerate, shortlist toggles,
  // detail-select, confirm-selection, and chat compose. Backend CAS stays the
  // authoritative guard; this is UX-only. `chatLedger.hasPendingSeed` folds in the
  // durable (reload-surviving) case, not just this session's own submit.
  const poolMutationBusy = $derived(
    poolMutationLocked
    || regenerating
    || isRegenerating
    || seedPending
    || chatLedger.hasPendingSeed
    || chatLedger.activeOperation?.kind === "SEED_IDEA"
    || chatLedger.hasPendingBatch,
  );

  function stopSeedPoll() {
    if (seedPollTimer) {
      clearInterval(seedPollTimer);
      seedPollTimer = null;
    }
  }

  function scrollBehavior(): ScrollBehavior {
    return typeof window.matchMedia === "function"
      && window.matchMedia("(prefers-reduced-motion: reduce)").matches
      ? "auto"
      : "smooth";
  }

  function scrollAndHighlightSolution(name: string) {
    seedHighlightName = name;
    requestAnimationFrame(() => {
      for (const row of document.querySelectorAll<HTMLElement>("[data-solution-name]")) {
        if (row.dataset.solutionName === name) {
          row.scrollIntoView({ behavior: scrollBehavior(), block: "center" });
          break;
        }
      }
    });
    setTimeout(() => {
      if (seedHighlightName === name) seedHighlightName = null;
    }, 4000);
  }

  function scrollAndHighlightRuledOut(index: number) {
    // The ruled-out list lives inside the collapsed appendix on the owner view —
    // open it first so the target row exists before the scroll query runs.
    appendixExpanded = true;
    seedHighlightRuledOutIndex = index;
    requestAnimationFrame(() => {
      for (const row of document.querySelectorAll<HTMLElement>("[data-ruled-out-index]")) {
        if (row.dataset.ruledOutIndex === String(index)) {
          row.scrollIntoView({ behavior: scrollBehavior(), block: "center" });
          break;
        }
      }
    });
    setTimeout(() => {
      if (seedHighlightRuledOutIndex === index) seedHighlightRuledOutIndex = null;
    }, 4000);
  }

  function reviewBatchCandidates(ideaIds: string[]) {
    const available = ideaIds.filter((ideaId) =>
      solutions.some((solution) => solution.idea_id === ideaId));
    if (available.length === 0) return;
    batchHighlightIdeaIds = new Set(available);
    requestAnimationFrame(() => {
      const first = [...document.querySelectorAll<HTMLElement>("[data-idea-id]")]
        .find((row) => available.includes(row.dataset.ideaId ?? ""));
      first?.scrollIntoView({ behavior: scrollBehavior(), block: "center" });
    });
    setTimeout(() => {
      batchHighlightIdeaIds = new Set();
    }, 4000);
  }

  function reviewBatchRuledOut(operationId: string) {
    // `generation_operation_id` is the only key the worker stamps with a BATCH dispatch id;
    // dispatch_id/evaluation_id are seed-scoped and can never match one.
    const index = (examinedRuledOut ?? []).findIndex((finding) =>
      finding.generation_operation_id === operationId);
    if (index >= 0) scrollAndHighlightRuledOut(index);
    else {
      appendixExpanded = true;
      requestAnimationFrame(() => {
        document.getElementById("examined-ruled-out")
          ?.scrollIntoView({ behavior: scrollBehavior(), block: "start" });
      });
    }
  }

  function reviewEvaluationResult(evaluationId: string) {
    const finding = (examinedRuledOut ?? []).find((candidate) => (
      candidate.evaluation_id === evaluationId || candidate.dispatch_id === evaluationId
    ));
    if (finding) {
      openRuledOutDetail(finding);
      return;
    }
    selectError = "That evaluated result is no longer available in this report.";
  }

  function retryBatch(activity?: BatchActivityRecord) {
    if (!canRequestBatch || poolMutationBusy) return;
    regenerateFocus = activity?.focus ?? "auto";
    regenerateError = "";
    regenerateOverlayOpen = true;
  }

  let handledActivityDeepLink = "";
  $effect(() => {
    const evaluationId = page.url.searchParams.get("evaluationId");
    const operationId = page.url.searchParams.get("batchOperationId")
      ?? page.url.searchParams.get("reviewBatchRuledOut");
    const addBatch = page.url.searchParams.get("addBatch");
    const signature = evaluationId
      ? `evaluation:${evaluationId}`
      : operationId
        ? `ruled-out:${operationId}`
        : addBatch === "1"
          ? "add-batch"
          : "";
    if (!signature || handledActivityDeepLink === signature) return;
    handledActivityDeepLink = signature;
    queueMicrotask(() => {
      if (evaluationId) reviewEvaluationResult(evaluationId);
      else if (operationId) reviewBatchRuledOut(operationId);
      else retryBatch();
      const next = new URL(page.url);
      next.searchParams.delete("evaluationId");
      next.searchParams.delete("batchOperationId");
      next.searchParams.delete("reviewBatchRuledOut");
      next.searchParams.delete("addBatch");
      replaceState(`${next.pathname}${next.search}${next.hash}`, page.state);
    });
  });

  /** Set once settlement is detected; consumed by the $effect below once the
   *  parent's FORCED getSolutions()/getPreviewReport() refresh (onSeedSettled)
   *  lands new `solutions`/`examinedRuledOut` props. Reconciles by OUTCOME —
   *  "is there a row that wasn't here before" — never by re-diffing names in
   *  general (the SSE sorted-name-diff bug this plan explicitly avoids repeating;
   *  a brand-new seed's name is guaranteed novel, which is what makes this safe). */
  let pendingSeedReconcile = $state<{
    outcome: "accepted" | "demoted" | "failed" | "refunded";
    priorNames: Set<string>;
    priorRuledOutCount: number;
  } | null>(null);

  $effect(() => {
    const reconcile = pendingSeedReconcile;
    if (!reconcile) return;
    if (reconcile.outcome === "accepted") {
      const newName = solutions.map((s) => s.solution_name).find((n) => !reconcile.priorNames.has(n));
      if (newName) {
        pendingSeedReconcile = null;
        scrollAndHighlightSolution(newName);
      }
      // else: the forced refresh hasn't landed in props yet — this effect re-runs
      // the moment `solutions` changes.
    } else if (reconcile.outcome === "demoted") {
      if ((examinedRuledOut?.length ?? 0) > reconcile.priorRuledOutCount) {
        const idx = (examinedRuledOut ?? []).findIndex((f) => f.source_frame === "user_seed");
        pendingSeedReconcile = null;
        if (idx >= 0) scrollAndHighlightRuledOut(idx);
      }
    } else {
      pendingSeedReconcile = null;
    }
  });

  /** Identity of the in-flight seed, kept in reactive state so the settlement effect
   *  below can resolve the instant `chatLedger`'s shared store updates — not just on
   *  this component's own 6s tick. */
  let inFlightSeed = $state<{
    sourceMessageId: string;
    priorNames: Set<string>;
    priorRuledOutCount: number;
  } | null>(null);

  function settleSeed(
    outcome: "accepted" | "demoted" | "failed" | "refunded",
    priorNames: Set<string>,
    priorRuledOutCount: number,
  ) {
    // Idempotency guard: the reactive effect below and the interval tick in
    // beginSeedSettlementPoll can both observe the same `chatLedger.reload()` and race to
    // call this — whichever gets here first wins, the other becomes a no-op instead of
    // double-firing onSeedSettled.
    if (!inFlightSeed) return;
    stopSeedPoll();
    inFlightSeed = null;
    seedPollStalledId = null;
    seedPending = false;
    seedBanner = { outcome };
    pendingSeedReconcile = { outcome, priorNames, priorRuledOutCount };
    onSeedSettled?.(outcome);
  }

  // Reactive (primary) settlement signal: the job page's own SSE handler forces a
  // `chatLedger.reload()` the instant job.status arrives at AWAITING_SELECTION — this
  // effect resolves the moment that reload lands rather than waiting on the interval's
  // next 6s tick, since `chatLedger`'s outcome map is `$state` and shared across both
  // components. The interval in beginSeedSettlementPoll below is now a BACKSTOP for a
  // dropped/delayed SSE event, not the primary signal.
  $effect(() => {
    if (!inFlightSeed) return;
    const outcome = chatLedger.seedOutcome(inFlightSeed.sourceMessageId);
    if (outcome && outcome !== "pending") {
      settleSeed(outcome, inFlightSeed.priorNames, inFlightSeed.priorRuledOutCount);
    }
  });

  /** After a successful submit, poll the ledger for the durable settlement receipt
   *  (chatLedger reloads server history — the SAME mechanism that reconstructs
   *  applied-patch state, not a parallel client store). Backstop only (see the
   *  reactive effect above) — kept because SSE delivery isn't guaranteed. */
  function beginSeedSettlementPoll(sourceMessageId: string, priorNames: Set<string>, priorRuledOutCount: number) {
    if (
      inFlightSeed?.sourceMessageId === sourceMessageId
      && (seedPollTimer || seedPollStalledId === sourceMessageId)
    ) {
      return;
    }
    stopSeedPoll();
    inFlightSeed = { sourceMessageId, priorNames, priorRuledOutCount };
    seedPollStalledId = null;
    let attempts = 0;
    // ~20 minutes at 6s — a real seed run (tournament + score_wave + red-team + SEO
    // probes) routinely exceeds the old 4-minute ceiling. Generous because this is now
    // a backstop, not the primary signal.
    const MAX_ATTEMPTS = 200;
    seedPollTimer = setInterval(async () => {
      attempts++;
      await chatLedger.reload();
      const outcome = chatLedger.seedOutcome(sourceMessageId);
      if (outcome && outcome !== "pending") {
        settleSeed(outcome, priorNames, priorRuledOutCount);
      } else if (attempts >= MAX_ATTEMPTS) {
        // Record WHY it stopped. Clearing seedPending alone still left the durable
        // ledger pending — so poolMutationBusy stayed locked with no way forward
        // except a manual page reload.
        stopSeedPoll();
        seedPending = false;
        seedPollStalledId = sourceMessageId;
      }
    }, 6000);
  }

  async function recheckSeed() {
    const sourceMessageId = seedPollStalledId;
    const seed = inFlightSeed;
    if (!sourceMessageId || seed?.sourceMessageId !== sourceMessageId) return;
    seedPollStalledId = null;
    beginSeedSettlementPoll(
      sourceMessageId,
      seed.priorNames,
      seed.priorRuledOutCount,
    );
    await chatLedger.reload();
    const outcome = chatLedger.seedOutcome(sourceMessageId);
    if (outcome && outcome !== "pending") {
      settleSeed(outcome, seed.priorNames, seed.priorRuledOutCount);
    }
  }

  async function handleSeed(
    patch: NewIdeaSeedPatch | IdeaSynthesisPatch,
    sourceMessageId: string,
  ): Promise<boolean> {
    if (poolMutationBusy) return false;
    // `seedPending` (local) is the in-flight latch for THIS request — it locks the UI
    // the instant the button is clicked, before the server has even accepted it. Only
    // once seedIdea() actually SUCCEEDS does chatLedger get the durable "pending" mark
    // (see markSeedPending below) — marking it up front would leave the card stuck
    // showing "Evaluating…" forever after a 402/409/network failure, since there would
    // be no server receipt to ever move it out of that state.
    seedPending = true;
    seedError = "";
    seedBanner = null;
    chatThreadRef?.stopStreaming();
    const priorNames = new Set(solutions.map((s) => s.solution_name));
    const priorRuledOutCount = examinedRuledOut?.length ?? 0;
    try {
      await seedIdea(
        jobId,
        patch.kind === 'idea_synthesis'
          ? {
              kind: 'idea_synthesis',
              sourceMessageId,
              expectedCost: seedCost ?? 0,
            }
          : {
              free_text: patch.free_text,
              pain_ref: patch.pain_ref,
              tool_ref: patch.tool_ref,
              rationale: patch.rationale,
              sourceMessageId,
              expectedCost: seedCost ?? 0,
            },
      );
      chatLedger.markSeedPending(sourceMessageId);
      beginSeedSettlementPoll(sourceMessageId, priorNames, priorRuledOutCount);
      return true;
    } catch (e) {
      seedPending = false;
      if (e instanceof ApiError && e.status === 402) {
        const body = e.details as { balance?: number; required?: number } | undefined;
        creditTopUp.show({
          balance: body?.balance ?? creditBalance,
          required: body?.required ?? seedCost ?? 0,
          stageName: "idea evaluation",
        });
      } else if (e instanceof ApiError && e.status === 409) {
        try {
          const fresh = await getStageCosts();
          seedCostOverride = fresh.seed_idea ?? null;
          seedError = PRICE_CHANGED_RETRY;
        } catch {
          seedError = PRICE_CHANGED_RELOAD;
        }
      } else {
        seedError = e instanceof Error ? e.message : "Failed to submit your idea";
      }
      return false;
    }
  }

  function resolveAcceptedVariant(
    patch: IdeaSynthesisPatch,
    receipt: SeedResultSummary,
    sourceMessageId: string,
  ): { parents: SolutionPreview[]; child: SolutionPreview } | null {
    if (
      !receipt.idea_id
      || !receipt.idea_revision
      || receipt.synthesis_operation !== patch.operation
      || receipt.synthesis_source_message_id !== sourceMessageId
    ) return null;

    const expectedKeys = patch.parents.map((parent) => `${parent.ideaId}:${parent.ideaRevision}`);
    const receiptKeys = (receipt.synthesized_from ?? []).map(
      (parent) => `${parent.idea_id}:${parent.idea_revision}`,
    );
    if (
      new Set(expectedKeys).size !== expectedKeys.length
      || receiptKeys.length !== expectedKeys.length
      || !expectedKeys.every((key) => receiptKeys.includes(key))
    ) return null;

    const parents = patch.parents.map((parentRef) => solutions.find((idea) =>
      idea.idea_id === parentRef.ideaId
      && (idea.idea_revision ?? 1) === parentRef.ideaRevision
    ));
    if (parents.some((parent) => !parent)) return null;
    const child = solutions.find((idea) =>
      idea.idea_id === receipt.idea_id
      && (idea.idea_revision ?? 1) === receipt.idea_revision
      && idea.synthesis_operation === patch.operation
      && idea.synthesis_source_message_id === sourceMessageId
      && idea.synthesized_from?.length === expectedKeys.length
      && expectedKeys.every((key) => idea.synthesized_from?.some(
        (candidate) => `${candidate.idea_id}:${candidate.idea_revision}` === key,
      ))
    );
    return child ? { parents: parents as SolutionPreview[], child } : null;
  }

  function addVariantToShortlist(
    parents: SolutionPreview[],
    child: SolutionPreview,
  ): { ok: boolean; message?: string } {
    if (selectLoading || poolMutationBusy) {
      return { ok: false, message: "Another idea update is still running." };
    }
    const parentKeys = new Set(parents.map(ideaKey));
    const childKey = ideaKey(child);
    if (selectedIdeaKeys.has(childKey)) {
      return { ok: true, message: "Variant is already in your shortlist." };
    }
    const selectedParents = parents.filter((parent) => selectedIdeaKeys.has(ideaKey(parent)));
    if (selectedParents.length) {
      const orderedKeys = Array.from(selectedIdeaKeys);
      selectedIdeaKeys.clear();
      let insertedChild = false;
      for (const key of orderedKeys) {
        if (parentKeys.has(key)) {
          if (!insertedChild) selectedIdeaKeys.add(childKey);
          insertedChild = true;
        } else {
          selectedIdeaKeys.add(key);
        }
      }
      queueShortlistSave();
      return {
        ok: true,
        message: selectedParents.length === 1
          ? `Replaced ${solutionDisplayTitle(selectedParents[0])} with the evaluated variant.`
          : `Replaced ${selectedParents.length} source ideas with the combined variant.`,
      };
    }
    if (selectedIdeaKeys.size >= MAX_SELECTIONS) {
      return { ok: false, message: "Shortlist is full. Remove one idea first." };
    }
    selectedIdeaKeys.add(childKey);
    queueShortlistSave();
    return { ok: true, message: "Variant added to your shortlist." };
  }
  function handleReviewVariant(
    patch: IdeaSynthesisPatch,
    receipt: SeedResultSummary,
    sourceMessageId: string,
  ): { ok: boolean; message?: string } {
    const resolved = resolveAcceptedVariant(patch, receipt, sourceMessageId);
    if (!resolved) {
      return { ok: false, message: "The evaluated variant is still syncing. Refresh and try again." };
    }
    void goto(selectionWorkspaceHref("compare", {
      view: "market",
      ideas: [...resolved.parents, resolved.child],
    }));
    return { ok: true };
  }

  function handleUseVariant(
    patch: IdeaSynthesisPatch,
    receipt: SeedResultSummary,
    sourceMessageId: string,
  ): { ok: boolean; message?: string } {
    const resolved = resolveAcceptedVariant(patch, receipt, sourceMessageId);
    return resolved
      ? addVariantToShortlist(resolved.parents, resolved.child)
      : { ok: false, message: "The evaluated variant is still syncing. Refresh and try again." };
  }

  // A live poll interval must not outlive the component (navigating away mid-evaluation).
  $effect(() => {
    return () => stopSeedPoll();
  });

  // ── Derived display values ──
  const shape = $derived(opportunityShape(solutions));
  const deepCost = $derived(stageCosts.deep_research);
  const canAffordDeep = $derived(creditBalance >= deepCost);
  const selectionCount = $derived(selectedIdeaKeys.size);
  const canSubmit = $derived(selectionCount > 0);
  const analystLauncherLabel = ASK_ANALYST_LABEL;
  const bestScore = $derived.by(() => {
    const scores = solutions
      .map((solution) => displayCompositeScore(solution))
      .filter((score): score is number => score != null);
    return scores.length ? Math.round(Math.max(...scores) * 100) : null;
  });
  const seedActivities = $derived(chatLedger.seedActivities);
  const synthesisActivities = $derived(
    seedActivities.filter((activity) => activity.kind === "idea_synthesis"),
  );
  // A durable submitted receipt survives reloads and route changes. Re-arm the same
  // settlement backstop when this component remounts; a stalled watcher stays stalled
  // until the owner explicitly asks for another check.
  $effect(() => {
    if (chatLedger.jobId !== jobId) return;
    const pending = seedActivities.find((activity) => activity.outcome === "pending");
    if (!pending || seedPollStalledId === pending.sourceMessageId) return;
    beginSeedSettlementPoll(
      pending.sourceMessageId,
      new Set(solutions.map((solution) => solution.solution_name)),
      examinedRuledOut?.length ?? 0,
    );
  });
  const batchActivities = $derived(chatLedger.batchActivities);
  $effect(() => {
    const pending = batchActivities.find((activity) => activity.outcome === "pending");
    if (pending) beginBatchPoll(pending.operationId);
  });
  const settledSynthesisActivities = $derived(
    synthesisActivities.filter((activity) => activity.outcome !== "pending"),
  );
  const cmdStatsLine = $derived(
    candidateStatsLine({ candidates: solutions.length, topScore: bestScore, segments: segmentCount }),
  );
  /** The always-visible receipt for paid evaluations: a tally in the header that opens
   *  the record below, so settled results need no permanent block above the candidates. */
  const evaluatedDirectionsLabel = $derived(
    settledSynthesisActivities.length > 0
      ? `${settledSynthesisActivities.length} evaluated `
        + `${settledSynthesisActivities.length === 1 ? "direction" : "directions"}`
      : "",
  );

  function openEvaluationRecord() {
    document.getElementById("evaluation-record")
      ?.scrollIntoView({ behavior: scrollBehavior(), block: "start" });
  }

  /** The ruled-out list lives inside the collapsed appendix, so a pointer to it has to
   *  open the disclosure — otherwise "it is listed under Examined and ruled out" sends
   *  the reader to a heading with nothing under it. */
  function openExaminedRuledOut() {
    appendixExpanded = true;
    requestAnimationFrame(() => {
      document.getElementById("examined-ruled-out")
        ?.scrollIntoView({ behavior: scrollBehavior(), block: "start" });
    });
  }
  const detailEvidenceLinks = $derived.by(() => {
    const base = `/jobs/${encodeURIComponent(jobId)}`;
    const links: { href: string; label: string }[] = [];
    if ((painPointCount ?? 0) > 0) links.push({ href: `${base}#pain-points`, label: "Pain evidence" });
    if ((segmentCount ?? 0) > 0) links.push({ href: `${base}#audience`, label: "Audience evidence" });
    return links;
  });

  // ── Below-table IA (Phase 1b, owner view only) ──
  // The analyst verdict pull-quote and the opportunity-shape line stay visible;
  // everything else regroups into the collapsed dossier appendix. The visitor
  // view (interactive={false}) keeps its original inline rendering untouched.
  let appendixExpanded = $state(false);
  const hasCoverageDisclosures = $derived(Boolean(
    (coverageNotes && coverageNotes.length)
      || (userAdjustments && userAdjustments.length)
      || marketReality?.incumbents?.length,
  ));
  const appendixMeta = $derived(appendixMetaLine({
    analystNotes: summarySupportingNotes.length,
    collaborator: collaboratorRationaleCount,
    ruledOut: examinedRuledOut?.length ?? 0,
  }));
  // Founder context below the table: display-only summary row once a profile
  // exists; the fuller card only while no profile is saved AND the guidance
  // spine is pointing at add_decision_context. Editing lives on the row's own
  // edit button in every variant (the editor overlay mounts in every variant).
  const briefVariant = $derived<"card" | "summary">(
    !activeDecisionProfile && selectionDecisionState?.nextAction?.kind === "add_decision_context"
      ? "card"
      : "summary",
  );
  const selectedIdeas = $derived.by(() =>
    Array.from(selectedIdeaKeys)
      .map(solutionForKey)
      .filter((solution): solution is SolutionPreview => Boolean(solution)),
  );
  // Near-duplicate shortlist entries stay in the selection flow rather than only in
  // the dossier appendix, where they could be missed before the commit gate.
  const shortlistOverlapWarnings = $derived(
    shortlistOverlaps(
      overlapGroups,
      selectedIdeas.map((idea) => ({
        name: idea.solution_name,
        label: solutionDisplayTitle(idea),
      })),
    ),
  );
  const analystSelectionContext = $derived<SelectionWorkspaceContext>({
    workspace: "candidates",
    ideas: selectedIdeas
      .filter((idea) => Boolean(idea.idea_id))
      .slice(0, MAX_SELECTIONS)
      .map((idea) => ({
        ideaId: idea.idea_id!,
        ideaRevision: idea.idea_revision ?? 1,
      })),
  });
  const selectionJourney = $derived.by(() => {
    if (!selectionDecisionState) return null;
    const localShortlist = selectedIdeas
      .filter((idea) => Boolean(idea.idea_id))
      .slice(0, MAX_SELECTIONS)
      .map((idea) => ({
        ideaId: idea.idea_id!,
        ideaRevision: idea.idea_revision ?? 1,
        title: solutionDisplayTitle(idea),
      }));
    return buildSelectionJourney({
      ...selectionDecisionState,
      shortlist: {
        ...selectionDecisionState.shortlist,
        items: localShortlist,
      },
    }, decisionTools);
  });
  $effect(() => {
    onJourneyTasks?.(selectionJourney?.tasks);
  });
  $effect(() => {
    onShortlistChange?.(selectionCount);
  });
  // DecisionBrief is the sole build-limits owner in both card and saved-summary
  // variants. This progress list reports only the remaining optional checks.
  const decisionHomeTasks = $derived.by(() =>
    (selectionJourney?.tasks ?? []).filter((task) =>
      task.key === "compare" || task.key === "risks"
    ),
  );
  const decisionHomeRecommendation = $derived.by(() => {
    const recommendation = selectionJourney?.recommendation;
    if (!recommendation) return null;
    return recommendation.target === "shortlist"
      || recommendation.target === "constraints"
      || recommendation.target === "compare"
      || recommendation.target === "risks"
      ? recommendation
      : null;
  });
  // The build-limits card owns the add_decision_context recommendation surface,
  // so the guide defers to it (no duplicate constraints heading/CTA on the hub).
  const hubRecommendation = $derived(
    briefVariant === "card" ? null : decisionHomeRecommendation,
  );
  // Overlap groups where every variant is still a separate visible candidate — the merge
  // was proposed but rejected, so surface it as a pick-between-these hint.
  type ResolvedOverlapGroup = {
    ideaNames: string[];
    sharedProduct: string;
    comparisonIdeas: SolutionPreview[];
  };

  const rejectedOverlapGroups = $derived.by(() => {
    const groups: ResolvedOverlapGroup[] = [];
    for (const group of overlapGroups ?? []) {
      if (group.idea_names.length < 2) continue;
      const matches = group.idea_names.map((name) =>
        solutions.filter((solution) => solution.solution_name === name),
      );
      if (matches.some((candidates) => candidates.length === 0)) continue;
      const exactIdeas = matches.every((candidates) => candidates.length === 1)
        ? matches.map((candidates) => candidates[0])
        : [];
      groups.push({
        ideaNames: group.idea_names,
        sharedProduct: group.shared_product,
        comparisonIdeas: exactIdeas.length >= 2 && exactIdeas.length <= MAX_SELECTIONS
          ? exactIdeas
          : [],
      });
    }
    return groups;
  });

  /** Anything at all filed in the dossier appendix (owner view). Declared after
   *  `rejectedOverlapGroups` so TS sees the dependency as assigned. */
  const appendixHasContent = $derived(
    summarySupportingNotes.length > 0
      || collaboratorFeedbackGroups.length > 0
      || rejectedOverlapGroups.length > 0
      || (examinedRuledOut?.length ?? 0) > 0
      || hasCoverageDisclosures,
  );

  function openOverlapComparison(group: ResolvedOverlapGroup): void {
    if (group.comparisonIdeas.length < 2) return;
    void goto(selectionWorkspaceHref("compare", {
      view: "market",
      ideas: group.comparisonIdeas,
    }));
  }

  // Parse the incumbent name out of a parity finding string, e.g.
  // "shipped by Aftershoot: ..." / "partial by Aftershoot: ..." → "Aftershoot",
  // "substitute (Forrager): ..." → "Forrager".
  function incumbentName(parity: string): string {
    const shipped = parity.match(/^(?:shipped by|partial by)\s+(.+?):/i);
    if (shipped) return shipped[1].trim();
    const substitute = parity.match(/^substitute\s*\(([^)]+)\)/i);
    if (substitute) return substitute[1].trim();
    const colonIdx = parity.indexOf(":");
    return colonIdx > 0 ? parity.slice(0, colonIdx).trim() : parity.trim();
  }

  // ── Sorting ──
  type SortKey = "score" | "fit" | "feas" | "build";
  let sortKey = $state<SortKey>("score");
  let sortDir = $state<"asc" | "desc">("desc");
  function setSort(k: SortKey) {
    if (sortKey === k) {
      sortDir = sortDir === "desc" ? "asc" : "desc";
    } else {
      sortKey = k;
      sortDir = k === "build" ? "asc" : "desc";
    }
  }
  /** Accessible name for a sort button: states the action the next press performs. */
  function sortActionLabel(k: SortKey, label: string): string {
    if (sortKey !== k) return `Sort by ${label}`;
    return sortDir === "desc"
      ? `Sort by ${label}, ascending`
      : `Sort by ${label}, descending`;
  }
  function buildWeeks(s?: string | null): number {
    if (!s) return Infinity;
    const m = s.match(/(\d+(?:\.\d+)?)\s*(day|week|month|year)/i);
    if (!m) return Infinity;
    const n = parseFloat(m[1]);
    const u = m[2].toLowerCase();
    const mult = u.startsWith("day")
      ? 1 / 7
      : u.startsWith("week")
        ? 1
        : u.startsWith("month")
          ? 4.345
          : u.startsWith("year")
            ? 52
            : 1;
    return n * mult;
  }
  function sortValue(s: SolutionPreview, k: SortKey): number {
    if (k === "score") return displayCompositeScore(s) ?? -1;
    if (k === "fit") return s.market_fit_score ?? -1;
    if (k === "feas") return s.technical_feasibility_score ?? -1;
    return buildWeeks(s.estimated_development_time);
  }
  const sortedSolutions = $derived.by(() => {
    const arr = [...solutions];
    arr.sort((a, b) => {
      const va = sortValue(a, sortKey);
      const vb = sortValue(b, sortKey);
      return sortDir === "desc" ? vb - va : va - vb;
    });
    return arr;
  });

  // Detail links are durable, exact candidate references. Browser Back removes the
  // shallow detail entry; refresh/share restores the same revision and tab. Names are
  // accepted only for legacy candidates that have no stable id, and only when unique.
  $effect(() => {
    const requestedTab = page.url.searchParams.get("detailTab");
    const poolIdentity = sortedSolutions
      .map((solution) => ideaKey(solution))
      .join("|");
    const queryKey = `${jobId}:${page.url.pathname}:${page.url.search}:${poolIdentity}`;
    if (handledDetailQuery === queryKey) return;
    handledDetailQuery = queryKey;

    if (!requestedTab) {
      modalIndex = null;
      detailTab = "overview";
      detailHistoryOwned = false;
      return;
    }
    if (requestedTab !== "overview" && requestedTab !== "detail") {
      modalIndex = null;
      detailUrlError = "This idea-detail link requests a view that no longer exists.";
      detailHistoryOwned = false;
      return;
    }

    const ideaId = page.url.searchParams.get("ideaId");
    const revisionParam = page.url.searchParams.get("ideaRevision");
    const legacyName = page.url.searchParams.get("ideaName");
    let index = -1;

    if (ideaId) {
      const revision = Number(revisionParam);
      if (!revisionParam || !Number.isInteger(revision) || revision < 1) {
        modalIndex = null;
        detailUrlError = "This idea-detail link is missing a valid idea revision.";
        detailHistoryOwned = false;
        return;
      }
      index = sortedSolutions.findIndex((candidate) =>
        candidate.idea_id === ideaId
        && (candidate.idea_revision ?? 1) === revision
      );
    } else if (legacyName) {
      const matches = sortedSolutions
        .map((candidate, candidateIndex) => ({ candidate, candidateIndex }))
        .filter(({ candidate }) =>
          !candidate.idea_id && candidate.solution_name === legacyName
        );
      if (matches.length === 1) index = matches[0].candidateIndex;
      else if (matches.length > 1) {
        modalIndex = null;
        detailUrlError = "This older name-only link is ambiguous. Open the exact idea from the ranked list.";
        detailHistoryOwned = false;
        return;
      }
    } else {
      modalIndex = null;
      detailUrlError = "This idea-detail link does not identify an idea.";
      detailHistoryOwned = false;
      return;
    }

    if (index < 0) {
      modalIndex = null;
      detailUrlError = "That exact idea revision is no longer available. Return to the ranked ideas to choose a current one.";
      detailHistoryOwned = false;
      return;
    }

    modalIndex = index;
    detailTab = requestedTab;
    detailUrlError = "";
  });

  // Suggested questions name the ACTUAL ranked candidates and the actions open right
  // now (shortlist, regenerate, or step back and question the niche) — recomputed as
  // the ranking, the shortlist, and the conversation change.
  const chatSuggestions = $derived(
    selectionSuggestions({
      solutions: sortedSolutions,
      messages: chatLedger.segmentMessages(5),
      weakPool,
      canRegenerate: canRequestBatch && !regenerating && !isRegenerating,
      hasSelection: selectionCount > 0,
      collaboratorRationaleCount,
      poolMutationBusy,
    }),
  );

  const SORT_COLS: { key: SortKey; label: string; tooltip?: string }[] = [
    // "/100" because the neighbouring columns render as percentages: a bare "70"
    // beside "60%" and "95%" reads as a third, unstated scale. Score is a relative
    // 0-100 ranking index, not a percentage, so it is labelled rather than converted.
    { key: "score", label: "Score /100", tooltip: SCORE_DEFINITIONS.composite },
    { key: "fit", label: "Market fit", tooltip: SCORE_DEFINITIONS.market_fit },
    {
      key: "feas",
      label: "Feasibility",
      tooltip: SCORE_DEFINITIONS.technical_feasibility,
    },
    { key: "build", label: "Build time" },
  ];

  // ── Helpers ──
  function selectionIndexOf(key: string): number {
    let i = 1;
    for (const selectedKey of selectedIdeaKeys) {
      if (selectedKey === key) return i;
      i++;
    }
    return 0;
  }
  function rankedIndexOf(solution: SolutionPreview): number {
    return sortedSolutions.findIndex((candidate) =>
      candidate.idea_id && solution.idea_id
        ? candidate.idea_id === solution.idea_id
          && (candidate.idea_revision ?? 1) === (solution.idea_revision ?? 1)
        : candidate === solution,
    );
  }
  function toggle(key: string) {
    if (selectLoading || poolMutationBusy) return;
    let changed = false;
    if (selectedIdeaKeys.has(key)) {
      changed = selectedIdeaKeys.delete(key);
    } else if (selectedIdeaKeys.size < MAX_SELECTIONS) {
      selectedIdeaKeys.add(key);
      changed = true;
    }
    if (changed) queueShortlistSave();
  }
  function handleToggleAdapter(solution: SolutionPreview) {
    toggle(ideaKey(solution));
  }
  // Overlay exclusivity: exactly one of these surfaces is open at a time.
  // Every opener below resets through here BEFORE assigning its own payload,
  // so a payload set before this call would be wiped out — never touch state
  // owned by this list until after calling it. chatPanel is never touched
  // here; its dock/expand/close state is independent of overlay exclusivity.
  function closeAllOverlays(preserveDetailUrl = false): void {
    const hadDetail = modalIndex !== null || page.url.searchParams.has("detailTab");
    modalIndex = null;
    detailTab = "overview";
    if (!preserveDetailUrl && hadDetail) {
      detailHistoryOwned = false;
      clearDetailUrl();
    }
    ruledOutDetail = null;
    regenerateOverlayOpen = false;
    copilotShortlistReview = null;
    copilotShortlistError = "";
    decisionBriefRef?.closeEditor?.();
  }

  function detailUrl(solution: SolutionPreview, tab: "overview" | "detail"): string {
    const next = new URL(page.url);
    next.searchParams.set("detailTab", tab);
    if (solution.idea_id) {
      next.searchParams.set("ideaId", solution.idea_id);
      next.searchParams.set("ideaRevision", String(solution.idea_revision ?? 1));
      next.searchParams.delete("ideaName");
    } else {
      next.searchParams.delete("ideaId");
      next.searchParams.delete("ideaRevision");
      next.searchParams.set("ideaName", solution.solution_name);
    }
    return `${next.pathname}${next.search}${next.hash}`;
  }

  function clearDetailUrl(hash?: string): void {
    const next = new URL(page.url);
    for (const key of ["detailTab", "ideaId", "ideaRevision", "ideaName"]) {
      next.searchParams.delete(key);
    }
    if (hash !== undefined) next.hash = hash;
    replaceState(`${next.pathname}${next.search}${next.hash}`, page.state);
  }

  function openDetail(solution: SolutionPreview) {
    closeAllOverlays(true);
    const index = rankedIndexOf(solution);
    if (index < 0) {
      detailUrlError = "That idea revision is no longer in this research run.";
      return;
    }
    modalIndex = index;
    detailTab = "overview";
    detailUrlError = "";
    detailHistoryOwned = true;
    pushState(detailUrl(sortedSolutions[index], "overview"), page.state);
  }

  function openDetailByKey(key: string) {
    const solution = solutionForKey(key);
    if (solution) {
      openDetail(solution);
    } else {
      detailUrlError = "That exact idea revision is no longer in this research run.";
    }
  }

  function handleNavigate(index: number) {
    const next = sortedSolutions[index];
    if (!next) return;
    modalIndex = index;
    replaceState(detailUrl(next, detailTab), page.state);
  }

  function handleDetailTabChange(tab: "overview" | "detail") {
    if (modalIndex === null) return;
    const current = sortedSolutions[modalIndex];
    if (!current) return;
    detailTab = tab;
    replaceState(detailUrl(current, tab), page.state);
  }

  function handleCloseDetail() {
    modalIndex = null;
    detailTab = "overview";
    detailUrlError = "";
    if (detailHistoryOwned) {
      detailHistoryOwned = false;
      window.history.back();
    } else {
      clearDetailUrl();
    }
    restoreChatAfterDetail();
  }

  async function handleOpenDetailEvidence(href: string) {
    const targetUrl = new URL(href, page.url);
    const targetId = decodeURIComponent(targetUrl.hash.slice(1));
    if (!targetId) return;

    modalIndex = null;
    detailTab = "overview";
    detailUrlError = "";
    detailHistoryOwned = false;
    clearDetailUrl(targetUrl.hash);
    restoreChatAfterDetail();

    await tick();
    const target = document.getElementById(targetId);
    if (!target) return;

    const trigger = target.querySelector<HTMLButtonElement>(
      "button[aria-expanded][aria-controls]",
    );
    if (trigger && trigger.getAttribute("aria-expanded") !== "true") {
      trigger.click();
      await tick();
    }

    target.scrollIntoView?.({ behavior: scrollBehavior(), block: "start" });
    trigger?.focus({ preventScroll: true });
  }

  function clearDetailUrlError() {
    detailUrlError = "";
    clearDetailUrl();
  }
  function openRuledOutDetail(finding: RuledOutFinding) {
    closeAllOverlays();
    ruledOutDetail = finding;
  }
  function handleCloseRuledOutDetail() {
    ruledOutDetail = null;
    restoreChatAfterDetail();
  }
  function restoreChatAfterDetail() {
    const state = returnToChatState;
    returnToChatState = null;
    if (state === "expanded") {
      chatPanel.expand();
    } else if (state === "docked") {
      chatPanel.dock();
    }
  }

  function openIdeaReference(reference: IdeaReference) {
    if (reference.kind === "ranked" && reference.solutionName) {
      const matches = solutions.filter((solution) =>
        solution.solution_name === reference.solutionName
      );
      if (matches.length === 1) {
        openDetail(matches[0]);
      } else {
        detailUrlError = matches.length === 0
          ? "That referenced idea is no longer in this research run."
          : "That legacy reference matches more than one idea. Open the exact idea from the ranked list.";
      }
      return;
    }
    if (reference.kind === "ruled-out" && reference.ruledOutIndex !== undefined) {
      const finding = examinedRuledOut?.[reference.ruledOutIndex];
      if (finding) openRuledOutDetail(finding);
    }
  }

  function openChatIdeaReference(reference: IdeaReference) {
    returnToChatState = chatPanel.isExpanded ? "expanded" : "docked";
    chatPanel.close();
    openIdeaReference(reference);
  }

  function handleValidate() {
    if (!canSubmit || poolMutationBusy) return;
    closeAllOverlays();
    void goto(selectionWorkspaceHref("review"));
  }

  function openFounderContext() {
    closeAllOverlays();
    decisionBriefRef?.openEditor();
  }

  function openExperimentWorkspace() {
    closeAllOverlays();
    const idea = selectedIdeas[0];
    void goto(selectionWorkspaceHref("risks", {
      tool: "tests",
      focus: idea?.idea_id ? { ideaId: idea.idea_id, ideaRevision: idea.idea_revision ?? 1 } : null,
    }));
  }


  function selectionWorkspaceHref(
    workspace: "compare" | "risks" | "review",
    options?: {
      view?: "market" | "founder";
      /** Opens a tool on arrival. The workspace strips these once handled, so
       *  they never linger as stale overlay state in the URL. */
      tool?: "compare" | "fit" | "challenge" | "assumptions" | "tests" | "variants";
      lens?: SelectionChallengeLens | null;
      focus?: { ideaId: string; ideaRevision: number } | null;
      assumptionId?: string;
      challengeId?: string;
      questionId?: string;
      mode?: SelectionConceptForgePrefill["purpose"];
      ideas?: SolutionPreview[];
    },
  ): string {
    // Single chokepoint for every hub-side deep link. Without the decision tools grant
    // the gated destinations are rewritten to the always-available compare view rather
    // than emitted as links the workspace would have to bounce back.
    if (!decisionTools) {
      if (workspace === "risks") workspace = "compare";
      options = {
        ...options,
        view: options?.view === "founder" ? "market" : options?.view,
        tool: options?.tool === "compare" ? "compare" : undefined,
        lens: null,
        assumptionId: undefined,
        challengeId: undefined,
        questionId: undefined,
        mode: undefined,
      };
    }
    const params = new URLSearchParams();
    // Review is the commit gate for the persisted shortlist, never an ad-hoc URL scope.
    // Keeping it bare also gives the gate one stable, bookmarkable route identity.
    if (workspace !== "review") {
      for (const idea of (options?.ideas ?? selectedIdeas).slice(0, MAX_SELECTIONS)) {
        if (idea.idea_id) params.append("idea", `${idea.idea_id}:${idea.idea_revision ?? 1}`);
      }
    }
    if (options?.view) params.set("view", options.view);
    if (options?.tool) params.set("tool", options.tool);
    if (options?.lens) params.set("lens", options.lens);
    if (options?.focus) {
      params.set("ideaId", options.focus.ideaId);
      params.set("ideaRevision", String(options.focus.ideaRevision));
    }
    if (options?.assumptionId) params.set("assumptionId", options.assumptionId);
    if (options?.challengeId) params.set("challengeId", options.challengeId);
    if (options?.questionId) params.set("questionId", options.questionId);
    if (options?.mode) params.set("mode", options.mode);
    const query = params.toString();
    return `/jobs/${encodeURIComponent(jobId)}/selection/${workspace}${query ? `?${query}` : ""}`;
  }

  function jobPageToolState(): App.PageState {
    return {
      ...page.state,
      selectionToolOrigin: createSelectionToolOrigin(page.url, jobId),
    };
  }

  /**
   * `?selectionTool=` used to be how the workspace pages reached their tools:
   * they navigated BACK here, which re-opened the tool over the job page rather
   * than the page the user launched it from. The workspace now hosts its own
   * tools and nothing links here that way any more; the handler stays only so
   * existing bookmarks keep working.
   *
   * Durable tools are redirected to their canonical route and query state.
   * Only bounded job-page actions (constraints and analyst) remain one-shot.
   */
  $effect(() => {
    if (!interactive) return;
    const tool = page.url.searchParams.get("selectionTool");
    if (!tool) return;
    const key = `${jobId}:${tool}:${page.url.search}`;
    if (handledSelectionToolQuery === key) return;
    handledSelectionToolQuery = key;

    const openTool = (): boolean => {
      // Stale bookmark into a tool this owner no longer has: drop the param and stay.
      if (!decisionTools && tool !== "analyst") return false;
      if (tool === "constraints") {
        openFounderContext();
        return false;
      }
      if (tool === "analyst") {
        chatPanel.open();
        return false;
      }
      const ideaId = page.url.searchParams.get("ideaId");
      const ideaRevision = Number(page.url.searchParams.get("ideaRevision") ?? "1");
      const focus = ideaId && Number.isInteger(ideaRevision) && ideaRevision >= 1
        ? { ideaId, ideaRevision }
        : null;
      const requestedLens = page.url.searchParams.get("lens");
      const lens = requestedLens === "demand"
        || requestedLens === "distribution"
        || requestedLens === "competition"
        || requestedLens === "dependencies"
        ? requestedLens
        : null;

      if (tool === "tests") {
        void goto(selectionWorkspaceHref("risks", {
          tool: "tests",
          focus,
          assumptionId: page.url.searchParams.get("assumptionId") ?? undefined,
        }), { replaceState: true });
        return true;
      }
      if (tool === "alternatives") {
        closeAllOverlays();
        void goto(selectionWorkspaceHref("compare", { tool: "variants" }), { replaceState: true });
        return true;
      }
      if (selectionCount === 0) return false;
      if (tool === "fit" || tool === "compare") {
        void goto(selectionWorkspaceHref("compare", { view: tool === "fit" ? "founder" : "market" }), { replaceState: true });
        return true;
      }
      if (tool === "assumptions" || tool === "risks") {
        void goto(selectionWorkspaceHref("risks", {
          tool: tool === "assumptions" ? "assumptions" : "challenge",
          focus,
          lens,
        }), { replaceState: true });
        return true;
      }
      return false;
    };

    queueMicrotask(() => {
      const navigated = openTool();
      if (!navigated) clearSelectionToolQuery();
    });
  });

  /** Drops the one-shot tool params without touching the rest of the query. */
  function clearSelectionToolQuery(): void {
    if (typeof window === "undefined") return;
    const next = new URL(page.url);
    let changed = false;
    for (const key of ["selectionTool", "ideaId", "ideaRevision", "assumptionId"]) {
      if (next.searchParams.has(key)) {
        next.searchParams.delete(key);
        changed = true;
      }
    }
    if (!changed) return;
    try {
      replaceState(`${next.pathname}${next.search}`, page.state);
    } catch {
      // replaceState needs an active SvelteKit router; harmless without one.
    }
  }

  function resolveDecisionStateIdeas(action: SelectionDecisionNextAction): SolutionPreview[] | null {
    const resolved = action.ideas.map(reference => solutions.find(solution =>
      solution.idea_id === reference.ideaId
      && (solution.idea_revision ?? 1) === reference.ideaRevision
    ));
    return resolved.every((idea): idea is SolutionPreview => Boolean(idea)) ? resolved : null;
  }

  function runSelectionDecisionAction(action: SelectionDecisionNextAction): void {
    if (poolMutationBusy || selectLoading) return;
    const ideas = resolveDecisionStateIdeas(action);
    if (!ideas) {
      selectionDecisionState = null;
      selectionDecisionStateError = "The idea changed while this suggestion was open. Refreshing it now.";
      void loadSelectionDecisionState();
      return;
    }

    if (action.kind === "select_candidate") {
      const idea = ideas[0];
      if (idea) openDetail(idea);
      return;
    }
    if (action.kind === "add_decision_context") {
      openFounderContext();
      return;
    }
    // Every tool below lives in the selection workspace. The recommendation
    // sends you to the same place the matching decision step does, so one tool
    // never has two different surfaces depending on where it was launched from.
    if (action.kind === "analyze_founder_fit") {
      if (ideas.length) void goto(selectionWorkspaceHref("compare", { view: "founder" }));
      return;
    }
    if (action.kind === "stress_test_evidence") {
      const idea = ideas[0];
      if (!idea?.idea_id || !action.lens) return;
      void goto(selectionWorkspaceHref("risks", {
        lens: action.lens,
        focus: { ideaId: idea.idea_id, ideaRevision: idea.idea_revision ?? 1 },
      }));
      return;
    }
    if (action.kind === "capture_assumption") {
      const idea = ideas[0];
      void goto(selectionWorkspaceHref("risks", {
        tool: "assumptions",
        lens: action.lens,
        focus: idea?.idea_id ? { ideaId: idea.idea_id, ideaRevision: idea.idea_revision ?? 1 } : null,
      }));
      return;
    }
    if (
      action.kind === "draft_test"
      || action.kind === "review_test_brief"
      || action.kind === "launch_test"
      || action.kind === "monitor_test"
      || action.kind === "record_conclusion"
    ) {
      const idea = ideas[0];
      void goto(selectionWorkspaceHref("risks", {
        tool: "tests",
        focus: idea?.idea_id ? { ideaId: idea.idea_id, ideaRevision: idea.idea_revision ?? 1 } : null,
        assumptionId: "assumptionId" in action && typeof action.assumptionId === "string"
          ? action.assumptionId
          : undefined,
      }));
      return;
    }
    handleValidate();
  }

  function resolveCopilotIdeas(action: SelectionCopilotAction): SolutionPreview[] | null {
    const resolved = action.ideas.map((reference) => solutions.find((solution) =>
      solution.idea_id === reference.ideaId
      && (solution.idea_revision ?? 1) === reference.ideaRevision
    ));
    return resolved.every((idea): idea is SolutionPreview => Boolean(idea)) ? resolved : null;
  }

  function handleCopilotAction(
    action: SelectionCopilotAction,
    sourceMessageId: string,
  ): { ok: boolean; message?: string } {
    // Unreachable in practice — without the grant the analyst never gets the
    // prepare_selection_action tool. Kept as a hard stop so a replayed or stale message
    // can't open a decision tool. `shortlist_review` is not a decision tool.
    if (!decisionTools && action.action !== "shortlist_review") {
      return { ok: false, message: "This tool is not available on your account." };
    }
    const resolvedIdeas = resolveCopilotIdeas(action);
    if (action.ideas.length > 0 && !resolvedIdeas) {
      return {
        ok: false,
        message: "This suggestion references an older idea revision. Refresh the research and ask the analyst again.",
      };
    }
    const ideas = resolvedIdeas ?? [];

    if (action.action === "shortlist_review") {
      if (typeof action.expectedVersion !== "number") {
        return { ok: false, message: "This shortlist suggestion is missing its source version. Ask the analyst to prepare it again." };
      }
      if (action.expectedVersion !== shortlistDraftVersion) {
        return { ok: false, message: "Your shortlist changed after this suggestion was prepared. Ask the analyst to review the current shortlist." };
      }
      if (ideas.length === 0 || ideas.length > MAX_SELECTIONS) {
        return { ok: false, message: "The suggested shortlist must contain between one and three current ideas." };
      }
      copilotShortlistError = "";
      copilotShortlistReview = {
        requestId: sourceMessageId,
        expectedVersion: action.expectedVersion,
        ideas,
        rationale: action.rationale,
        source: "analyst",
      };
      chatPanel.close();
      return { ok: true, message: "Review the shortlist diff before applying it." };
    }

    if (action.action === "prefill") {
      if (action.target === "concept_forge") {
        const purpose = action.values?.purpose;
        const targetTradeoff = action.values?.targetTradeoff;
        if (
          ideas.length < 1
          || ideas.length > 2
          || !["diverge", "resolve_tradeoff", "reshape"].includes(String(purpose))
          || (purpose === "resolve_tradeoff" && ideas.length !== 2)
          || (targetTradeoff !== undefined && typeof targetTradeoff !== "string")
        ) {
          return { ok: false, message: "This directions brief no longer matches one or two current ideas. Ask the analyst to prepare it again." };
        }
        closeAllOverlays();
        const prefill: SelectionConceptForgePrefill = {
          requestId: sourceMessageId,
          purpose: purpose as SelectionConceptForgePrefill["purpose"],
          targetTradeoff: typeof targetTradeoff === "string" ? targetTradeoff : "",
          rationale: action.rationale,
          caveats: action.caveats,
        };
        chatPanel.close();
        void goto(selectionWorkspaceHref("compare", {
          ideas,
          mode: prefill.purpose,
          tool: "variants",
        }), {
          state: { ...jobPageToolState(), selectionConceptPrefill: prefill },
        });
        return { ok: true, message: "Directions brief opened for review. Nothing has been generated or evaluated." };
      }
      if (action.target === "decision_profile") {
        // No closeAllOverlays here: reviewCopilotDraft owns its own dirty-check
        // (unsaved founder-context edits refuse a silent overwrite). Closing the
        // editor first would clear that guard out from under it.
        const result = decisionBriefRef?.reviewCopilotDraft(
          sourceMessageId,
          (action.values ?? {}) as Partial<SelectionDecisionProfile>,
        );
        if (result?.ok) chatPanel.close();
        return result ?? { ok: false, message: "The decision-context editor is not ready yet. Try again." };
      }
      if (action.target === "experiment") {
        const idea = ideas[0];
        if (!idea?.idea_id || ideas.length !== 1) {
          return { ok: false, message: "An experiment draft must reference exactly one current idea." };
        }
        closeAllOverlays();
        const draft = {
          ...(action.values ?? {}),
          ideaId: idea.idea_id,
          ideaRevision: idea.idea_revision ?? 1,
        } as SelectionExperimentDraftSeed;
        chatPanel.close();
        void goto(selectionWorkspaceHref("risks", {
          tool: "tests",
          focus: { ideaId: draft.ideaId, ideaRevision: draft.ideaRevision },
          assumptionId: draft.assumptionId ?? undefined,
        }), {
          state: { ...page.state, selectionTestDraft: draft },
        });
        return { ok: true, message: "Test draft opened for review. Nothing has been published." };
      }
      if (action.target === "assumption" || action.target === "owner_evidence") {
        const idea = ideas[0];
        if (!idea?.idea_id || ideas.length !== 1 || !action.lens) {
          return { ok: false, message: "This draft must reference one current idea and one evidence lens." };
        }
        const values = action.values ?? {};
        if (
          values.ideaId !== idea.idea_id
          || values.ideaRevision !== (idea.idea_revision ?? 1)
          || values.lens !== action.lens
        ) {
          return {
            ok: false,
            message: "The draft identity does not match its current idea revision and evidence lens.",
          };
        }

        if (action.target === "assumption") {
          const assumptionValues: SelectionAssumptionPrefill["values"] = {
            ...(typeof values.statement === "string" ? { statement: values.statement } : {}),
            ...(typeof values.impactIfFalse === "string" ? { impactIfFalse: values.impactIfFalse } : {}),
            ...(typeof values.falsificationQuestion === "string" ? { falsificationQuestion: values.falsificationQuestion } : {}),
          };
          const draftedFields = Object.keys(assumptionValues) as Array<keyof typeof assumptionValues>;
          if (
            draftedFields.length === 0
            || !action.grounding
            || draftedFields.some((field) => !action.grounding?.[field]?.length)
          ) {
            return {
              ok: false,
              message: "This assumption draft is missing current evidence references. Ask the analyst to prepare it again.",
            };
          }
          const assumptionPrefill: SelectionAssumptionPrefill = {
            requestId: sourceMessageId,
            ideaId: idea.idea_id,
            ideaRevision: idea.idea_revision ?? 1,
            lens: action.lens,
            record: action.record ? { id: action.record.id, version: action.record.version } : undefined,
            origin: action.origin,
            grounding: action.grounding,
            rationale: action.rationale,
            caveats: action.caveats,
            values: assumptionValues,
          };
          closeAllOverlays();
          chatPanel.close();
          void goto(selectionWorkspaceHref("risks", {
            tool: "assumptions",
            lens: action.lens,
            focus: { ideaId: idea.idea_id, ideaRevision: idea.idea_revision ?? 1 },
            ideas: [idea],
          }), {
            state: { ...page.state, selectionAssumptionPrefill: assumptionPrefill },
          });
          return { ok: true, message: "Assumption draft opened for review. Nothing has been saved." };
        }

        const ownerEvidencePrefill: SelectionOwnerEvidencePrefill = {
          requestId: sourceMessageId,
          ideaId: idea.idea_id,
          ideaRevision: idea.idea_revision ?? 1,
          lens: action.lens,
          origin: action.origin,
          values: values as SelectionOwnerEvidencePrefill["values"],
        };
        closeAllOverlays();
        chatPanel.close();
        void goto(selectionWorkspaceHref("risks", {
          lens: action.lens,
          focus: { ideaId: idea.idea_id, ideaRevision: idea.idea_revision ?? 1 },
          challengeId: action.origin?.challengeId,
          questionId: action.origin?.questionId,
          ideas: [idea],
        }), {
          state: { ...page.state, selectionOwnerEvidencePrefill: ownerEvidencePrefill },
        });
        return { ok: true, message: "Owner-evidence draft opened for review. Nothing has been added." };
      }
      return {
        ok: false,
        message: "This draft type cannot be safely prefilled yet. Open the workspace and enter it manually.",
      };
    }

    if (action.action !== "open") {
      return { ok: false, message: "This analyst action is not supported in the current workspace." };
    }

    if (action.target === "candidate") {
      const idea = ideas[0];
      if (!idea || ideas.length !== 1) {
        return { ok: false, message: "An idea action must reference exactly one current idea." };
      }
      returnToChatState = chatPanel.isExpanded ? "expanded" : "docked";
      chatPanel.close();
      openDetail(idea);
      return { ok: true };
    }

    if (action.target === "decision_profile") {
      // See the matching prefill branch above: reviewCopilotDraft's own
      // dirty-check is the guard here, not closeAllOverlays.
      const result = decisionBriefRef?.reviewCopilotDraft(sourceMessageId, {});
      if (result?.ok) chatPanel.close();
      return result ?? { ok: false, message: "The decision-context editor is not ready yet. Try again." };
    }

    if (action.target === "experiment" || action.target === "experiments") {
      if (ideas.length === 1 && ideas[0]?.idea_id) {
        closeAllOverlays();
        const draft: SelectionExperimentDraftSeed = {
          ideaId: ideas[0].idea_id,
          ideaRevision: ideas[0].idea_revision ?? 1,
        };
        chatPanel.close();
        void goto(selectionWorkspaceHref("risks", {
          tool: "tests",
          focus: { ideaId: draft.ideaId, ideaRevision: draft.ideaRevision },
        }), {
          state: { ...page.state, selectionTestDraft: draft },
        });
        return { ok: true };
      }
      chatPanel.close();
      openExperimentWorkspace();
      return { ok: true };
    }

    if (ideas.length === 0) {
      return { ok: false, message: "This action needs at least one current idea reference." };
    }

    const opensEvidence = action.target === "risk_queue"
      || action.target === "assumptions"
      || action.target === "assumption"
      || action.target === "challenge"
      || action.target === "owner_evidence";
    const opensFocusedEvidence = action.target === "challenge" || action.target === "owner_evidence";
    if (opensFocusedEvidence && (!action.lens || ideas.length !== 1 || !ideas[0].idea_id)) {
      return { ok: false, message: "An evidence action must include one current idea and an evidence lens." };
    }
    closeAllOverlays();
    chatPanel.close();
    if (opensEvidence) {
      const idea = ideas.length === 1 ? ideas[0] : null;
      void goto(selectionWorkspaceHref("risks", {
        tool: action.target === "assumptions" || action.target === "assumption"
          ? "assumptions"
          : undefined,
        lens: action.lens,
        focus: idea?.idea_id
          ? { ideaId: idea.idea_id, ideaRevision: idea.idea_revision ?? 1 }
          : null,
        challengeId: action.origin?.challengeId,
        questionId: action.origin?.questionId,
        ideas,
      }));
      return { ok: true };
    }
    void goto(selectionWorkspaceHref("compare", {
      view: action.target === "founder_fit" ? "founder" : "market",
      ideas,
    }));
    return { ok: true };
  }

  function applyCopilotShortlist(): void {
    const review = copilotShortlistReview;
    if (!review || shortlistSaveRunning) return;
    if (review.expectedVersion !== shortlistDraftVersion) {
      copilotShortlistError = "Your shortlist changed while this review was open. Close it and ask the analyst to review the latest shortlist.";
      return;
    }
    selectedIdeaKeys.clear();
    for (const idea of review.ideas) selectedIdeaKeys.add(ideaKey(idea));
    copilotShortlistReview = null;
    copilotShortlistError = "";
    queueShortlistSave();
  }

  function scoreColor(v: number | null): string {
    if (v == null) return "var(--color-text-muted)";
    if (v >= 0.7) return "var(--color-success-dark)";
    if (v < 0.35) return "var(--color-text-muted)";
    return "var(--color-text-primary)";
  }
  function pct(v?: number | null): string {
    return v == null ? "--" : String(Math.round(v * 100));
  }

  // Per-row derived helpers (called in snippet to keep markup lean)
  function rowMeta(s: SolutionPreview) {
    const sourcePain = s.source_pain?.trim()
      || s.pain_points_addressed?.[0]?.trim()
      || (s.unanchored_hypothesis ? "No validated pain match" : null);
    const riskKey =
      s.tags?.risk_flags?.[0]
        ?? (validatedBuildComplexity(s) === "high"
          ? "high"
          : validatedNoveltyLevel(s) === "conventional"
            ? "conventional"
            : null);
    const mergedFrom = s.idea_tier === "merged" ? (s.merged_from ?? []) : [];
    const parity = directIncumbentParity(s);
    const incumbent =
      parity
        ? { name: incumbentName(parity), full: parity }
        : null;
    const adversarial = adversarialReviewFinding(s);
    const synthesisParents = s.synthesized_from ?? [];
    const synthesisLabel = s.synthesis_operation
      ? {
          narrow: "Narrowed",
          reposition: "Repositioned",
          combine: "Combined",
          adjacent: "Adjacent",
        }[s.synthesis_operation]
      : null;
    return {
      title: solutionDisplayTitle(s),
      summary: solutionCardDescription(s),
      score: displayCompositeScore(s),
      fit: fitLabel(s.market_fit_score),
      feasPct: pct(s.technical_feasibility_score),
      build: s.estimated_development_time ?? "--",
      strength: solutionStrengthBadge(s),
      angle: s.winning_angle && angleLabel(s.winning_angle),
      strengthWhy: solutionPrimaryStrengthKey(s)
        ? tagDescription(solutionPrimaryStrengthKey(s))
        : null,
      angleWhy:
        s.angle_rationale ||
        (s.winning_angle ? angleDescription(s.winning_angle) : null),
      provenance: sourcePain,
      risk: riskKey
        ? { label: humanizeTag(riskKey), description: tagDescription(riskKey) }
        : null,
      mergedCount: mergedFrom.length,
      mergedNames: mergedFrom.join(", "),
      synthesisLabel,
      synthesisParents: synthesisParents.map((parent) => parent.solution_name).join(", "),
      incumbent,
      adversarial,
    };
  }
</script>

<div class="workbench-shell" data-annotation-anchor="research-workbench">
<div class="workbench" id="opportunities">
  <span id="solution-selector" class="workbench-anchor" aria-hidden="true"></span>
  <!-- ── Command header ── -->
  <header class="cmd" class:cmd-owner={interactive} data-annotation-anchor="shortlist-header">
    <div class="cmd-main">
      <!-- Stats fold into the title row as ONE record line (DESIGN_SYSTEM §5.1) —
           never a boxed stat-cell strip. Evidence counts (discussions, pain
           points, sources) live in the discovery-dossier ledger below. -->
      <div class="cmd-title-row">
        <h2 class="cmd-title">{interactive ? CHOOSE_IDEAS_LABEL : RANKED_LIST_HEADING}</h2>
        <p class="record-line cmd-stats" aria-label="Idea summary">
          {cmdStatsLine}{#if evaluatedDirectionsLabel} · <button
              type="button"
              class="cmd-stats-link"
              onclick={openEvaluationRecord}
            >{evaluatedDirectionsLabel}</button>{/if}
        </p>
      </div>
      {#if interactive}
        <p class="cmd-sub">
          Select one to three ideas. One Deep Research run covers the full shortlist; comparison and risk checks are optional.
        </p>
      {:else}
        <p class="cmd-sub">
          Solution ideas from the discovery run, ranked by composite score.
          Open a row for full detail and vote for the idea you like most.
        </p>
      {/if}
    </div>
    {#if !interactive}
      <aside class="cmd-status cmd-status--votes" aria-label="Vote status">
        <div class="vote-tally">
          <span class="vote-tally-num">{totalVotes}</span>
          <span class="vote-tally-label">vote{totalVotes === 1 ? "" : "s"} so far</span>
        </div>
        <p class="vote-tally-hint">Your vote helps the owner prioritize.</p>
      </aside>
    {/if}
  </header>

  <div class:selection-layout={interactive}>
    <div class="candidate-pool">
      <BatchActivity
        activities={batchActivities}
        stalledOperationId={batchPollStalledOperationId}
        onRecheck={recheckBatch}
        onReviewCandidates={reviewBatchCandidates}
        onReviewRuledOut={reviewBatchRuledOut}
        onRetry={canRequestBatch ? retryBatch : undefined}
      />
      <!-- Running evaluations only. Settled ones are provenance, not status, and live
           with the Discovery appendix so a rejected direction never outranks the
           candidates this page exists to choose between. -->
      <EvaluationActivity
        {jobId}
        activities={seedActivities}
        view="live"
        operation={chatLedger.activeOperation}
        stalled={seedPollStalledId != null}
        onRecheck={recheckSeed}
      />

      {#if detailUrlError}
        <div class="detail-link-error" role="alert">
          <p>{detailUrlError}</p>
          <button type="button" onclick={clearDetailUrlError}>Return to ranked ideas</button>
        </div>
      {/if}

      {#if regenerateError}
        <p class="regen-error" role="alert">{regenerateError}</p>
      {/if}

      {#if seedError}
        <p class="regen-error" role="alert">{seedError}</p>
      {/if}

      {#if seedBanner}
        <p class="seed-banner" role="status" class:seed-banner--accepted={seedBanner.outcome === "accepted"}>
          {#if seedBanner.outcome === "accepted"}
            Evaluation complete. The result was added to the ranked ideas below.
          {:else if seedBanner.outcome === "demoted"}
            We tested your idea. It didn't clear the market-fit bar. See why below.
          {:else}
            Evaluation failed. Your credits were refunded.
          {/if}
        </p>
      {/if}

      <!-- The whole optional-checks guide belongs to the decision tools grant. Without
           it there is no optional work to report, and the shortlist rail already carries
           "Review and start" — so the card would be an empty frame.
           Defined here, RENDERED below the ranked list: "what should I do next" and the
           analyst's read across the ideas both assume you have seen the ideas. -->
      {#snippet decisionGuideBlock()}
        <section class="decision-guide" aria-labelledby="decision-guide-title">
          <div class="decision-guide__copy">
            <p class="decision-guide__eyebrow">
              {hubRecommendation?.target === "shortlist" ? "Suggested next" : "Optional next check"}
            </p>
            {#if hubRecommendation}
              <h3 id="decision-guide-title">{hubRecommendation.title}</h3>
              <p>{hubRecommendation.description}</p>
              <!-- Always a launcher for the suggested step (every action kind is
                   handled by runSelectionDecisionAction), never a dead heading. -->
              {#if selectionDecisionState}
                <button
                  type="button"
                  class="decision-guide__candidate"
                  disabled={poolMutationBusy || selectLoading}
                  onclick={() => {
                    if (selectionDecisionState) runSelectionDecisionAction(selectionDecisionState.nextAction);
                  }}
                >
                  <!-- The evidence-check journey step reuses its heading as the
                       actionLabel; render a verb-forward CTA instead of the
                       identical text twice. Other kinds keep their own label. -->
                  {hubRecommendation.actionLabel === hubRecommendation.title
                    && hubRecommendation.actionLabel === STRESS_TEST_EVIDENCE_LABEL
                    ? "Run the check"
                    : hubRecommendation.actionLabel}
                </button>
              {/if}
            {:else if selectionDecisionStateLoading}
              <h3 id="decision-guide-title">Updating your next useful step…</h3>
            {:else}
              <h3 id="decision-guide-title">Your shortlist is ready when you are</h3>
              <p>The checks below are optional. They never change the Discovery ranking.</p>
            {/if}
          </div>

          <!-- Progress, not a second tool menu: the sidebar owns Compare / Check
               navigation; here each optional check reports its status only. -->
          {#if decisionHomeTasks.length}
            <ul class="decision-guide__progress" aria-label="Optional checks progress">
              {#each decisionHomeTasks as task (task.key)}
                <li class="decision-guide__progress-item">
                  <span class="decision-guide__progress-name">{task.title}</span>
                  <DecisionStatusBadge status={task.status} label={task.statusLabel} />
                </li>
              {/each}
            </ul>
          {/if}
        </section>

        {#if summaryRecommendation}
          <section class="discovery-take" aria-label="Discovery take">
            <p class="discovery-take__eyebrow">Discovery take · across all ideas</p>
            <p class="discovery-take__quote">
              <IdeaReferenceText
                content={summaryRecommendation}
                references={ideaReferences}
                onOpen={openIdeaReference}
              />
            </p>
          </section>
        {/if}
      {/snippet}

      {#if interactive && shortlistOverlapWarnings.length > 0}
        <section
          class="shortlist-overlap-notice"
          role="status"
          aria-label="Shortlist overlap"
        >
          {#each shortlistOverlapWarnings as overlap (overlap.sharedProduct)}
            <p>{overlapWarningText(overlap)}</p>
          {/each}
        </section>
      {/if}

      <!-- ── Ranked opportunity list ── -->
      <div
        class="opp-list"
        role="table"
        aria-label={RANKED_LIST_HEADING}
        data-annotation-anchor="shortlist-candidates"
      >
    <!-- Column header (desktop) -->
    <div class="opp-row opp-row-head" role="row" data-tour="ranked-list">
      <span class="cell-rank" role="columnheader">#</span>
      <span class="cell-select-label" role="columnheader">{interactive ? "Select" : "Vote"}</span>
      <span class="cell-title-label" role="columnheader">Idea</span>
      {#each SORT_COLS as col}
        <!-- Explicit name keeps the column name stable while the sibling help
             control exposes the metric definition on mouse hover and keyboard focus. -->
        <span
          class="cell-metric-shell"
          role="columnheader"
          aria-label={col.label}
          aria-sort={sortKey === col.key ? (sortDir === "asc" ? "ascending" : "descending") : "none"}
        >
          <button
            type="button"
            class="cell-metric-head"
            class:active={sortKey === col.key}
            onclick={() => setSort(col.key)}
            aria-label={sortActionLabel(col.key, col.label)}
          >
            <span>{col.label}</span>
            <!-- Always laid out, hidden while idle: an arrow that appears only on the
                 active column shrinks that column's label mid-interaction. -->
            <span class="sort-arrow" class:is-idle={sortKey !== col.key} aria-hidden="true">
              {#if sortKey === col.key && sortDir === "asc"}<ArrowUp class="w-3 h-3" />{:else}<ArrowDown class="w-3 h-3" />{/if}
            </span>
          </button>
          {#if col.tooltip}
            <Tooltip content={col.tooltip} position="bottom" class="metric-help" />
          {/if}
        </span>
      {/each}
    </div>

    {#each sortedSolutions as s, i (ideaKey(s))}
      {@const m = rowMeta(s)}
      {@const key = ideaKey(s)}
      {@const isSel = selectedIdeaKeys.has(key)}
      {@const maxed = !isSel && selectedIdeaKeys.size >= MAX_SELECTIONS}
      {@const isAnalystPick = analystPickNames.has(s.solution_name)}
      <div
        class="opp-row"
        role="row"
        class:opp-row-sel={isSel}
        class:opp-row-maxed={maxed}
        class:row-seed-highlight={seedHighlightName === s.solution_name}
        class:row-batch-highlight={Boolean(s.idea_id && batchHighlightIdeaIds.has(s.idea_id))}
        data-idea-id={s.idea_id}
        data-solution-name={s.solution_name}
        data-annotation-anchor={`candidate:${key}`}
      >
        <span class="cell-rank" role="cell">{i + 1}</span>

        {#if interactive}
          <span class="cell-shell" role="cell">
          <label
            class="cell-select select-control"
            data-tour={i === 0 ? "shortlist-checkbox" : undefined}
            class:sel={isSel}
            class:maxed
            aria-disabled={maxed ? "true" : undefined}
          >
            <input
              id={`idea-select-${i}`}
              type="checkbox"
              class="sr-only"
              checked={isSel}
              disabled={selectLoading || poolMutationBusy}
              aria-disabled={maxed ? "true" : undefined}
              aria-describedby={maxed ? `select-maxed-hint-${i}` : undefined}
              onchange={() => { if (!maxed) toggle(key); }}
              aria-label={isSel ? `Deselect ${m.title}` : `Select ${m.title}`}
            />
            {#if isSel}
              <span class="select-marker"><Check class="select-icon" strokeWidth={3} aria-hidden="true" /></span>
              <span class="select-copy">Selected</span>
            {:else if maxed}
              <span class="select-marker"><span class="select-dash" aria-hidden="true">-</span></span>
              <span class="select-copy">3 selected</span>
              <span id="select-maxed-hint-{i}" class="sr-only">Deselect one to add this</span>
            {:else}
              <span class="select-marker"><Plus class="select-icon" strokeWidth={2} aria-hidden="true" /></span>
              <span class="select-copy">Select</span>
            {/if}
          </label>
          </span>
        {:else}
          <span class="cell-select cell-action" role="cell">
            {#if actionSlot}{@render actionSlot({ solution: s, index: i })}{/if}
          </span>
        {/if}

        <span class="cell-shell" role="rowheader">
        <button
          type="button"
          class="cell-title"
          onclick={() => openDetail(s)}
        >
          <span class="sr-only">Review details for </span>
          <span
            class="title-block"
            data-annotation-anchor={`candidate:${key}:content`}
          >
            <span
              class="opp-title-line"
              data-annotation-anchor={`candidate:${key}:title`}
            >
              <span class="opp-title">{m.title}</span>
              {#if isAnalystPick}
                <span class="analyst-pick">Recommended</span>
              {/if}
            </span>
            <span class="opp-summary">{m.summary}</span>
            <span class="mobile-metrics">
              <span>Market <strong>{pct(s.market_fit_score)}{#if s.market_fit_score != null}%{/if}</strong></span>
              <span>Feas <strong>{m.feasPct}{#if s.technical_feasibility_score != null}%{/if}</strong></span>
              <span>Build <strong>{m.build}</strong></span>
            </span>
            {#if m.provenance}
              <span class="opp-evidence"><strong>Pain</strong><span>{m.provenance}</span></span>
            {/if}
            {#if m.mergedCount > 0}
              <Tooltip content={`Synthesized from: ${m.mergedNames}`} position="bottom" focusable={false}>
                {#snippet children()}
                  <span class="opp-merged-note">Synthesized from {m.mergedCount} variant{m.mergedCount === 1 ? "" : "s"}</span>
                {/snippet}
              </Tooltip>
            {/if}
            {#if m.synthesisLabel}
              <span class="opp-workshop-note">
                Workshop variant · {m.synthesisLabel}{#if m.synthesisParents}{" from "}{m.synthesisParents}{/if}
              </span>
            {/if}
            <span class="opp-tags">
              {#if m.strength}
                {@const strength = m.strength}
                {#if m.strengthWhy}
                  <Tooltip content={m.strengthWhy} position="bottom" focusable={false}>
                    {#snippet children()}<span class="tag tag-strength tag-{strength.variant}">{strength.label}</span>{/snippet}
                  </Tooltip>
                {:else}
                  <span class="tag tag-strength tag-{strength.variant}">{strength.label}</span>
                {/if}
              {/if}
              {#if m.angle}
                {@const angle = m.angle}
                <Tooltip content={m.angleWhy ?? ""} position="bottom" focusable={false}>
                  {#snippet children()}<span class="tag tag-angle">{angle}</span>{/snippet}
                </Tooltip>
              {/if}
              {#if m.incumbent}
                {@const incumbent = m.incumbent}
                <Tooltip content={incumbent.full} position="bottom" focusable={false}>
                  {#snippet children()}<span class="tag tag-parity">Incumbent: {incumbent.name}</span>{/snippet}
                </Tooltip>
              {/if}
              {#if m.adversarial}
                {@const adversarial = m.adversarial}
                <Tooltip
                  content={adversarial.details.join(" ") || "The adversarial review found a decision-critical objection."}
                  position="bottom"
                  focusable={false}
                >
                  {#snippet children()}<span class="tag tag-risk">{adversarial.label}</span>{/snippet}
                </Tooltip>
              {/if}
              {#if m.risk}
                {@const rowRisk = m.risk}
                <Tooltip content={rowRisk.description} position="bottom" focusable={false}>
                  {#snippet children()}<span class="tag tag-risk">{rowRisk.label}</span>{/snippet}
                </Tooltip>
              {/if}
            </span>
          </span>
        </button>
        </span>

        <!-- Score -->
        <span class="cell-metric metric-score" role="cell">
          <span class="metric-num" style:color={scoreColor(m.score)}>
            {m.score == null ? "--" : Math.round(m.score * 100)}
          </span>
        </span>

        <span class="cell-metric metric-fit" role="cell">
          <span class="metric-num fit-{m.fit.variant}">
            {pct(s.market_fit_score)}{#if s.market_fit_score != null}<span class="metric-unit">%</span>{/if}
          </span>
        </span>

        <span class="cell-metric" role="cell">
          <span class="metric-num">{m.feasPct}{#if s.technical_feasibility_score != null}<span class="metric-unit">%</span>{/if}</span>
        </span>

        <span class="cell-metric metric-build" role="cell">
          <span class="metric-num metric-build-num">{m.build}</span>
        </span>
      </div>

        {/each}
      </div>

      {#if interactive && decisionTools}
        {@render decisionGuideBlock()}
      {/if}

      <!-- A receipt for work the user paid for and started, so it stays a first-class
           section: below the candidates it reports on, never inside the collapsed
           "How the shortlist was formed" disclosure where it would be missed. Sitting
           next to "Add another batch" also puts what you tried beside how to try more. -->
      {#if interactive && settledSynthesisActivities.length > 0}
        <EvaluationActivity
          {jobId}
          activities={synthesisActivities}
          view="record"
          onOpenRuledOut={openExaminedRuledOut}
        />
      {/if}

      {#if interactive && (canRequestBatch || batchUsageKnown || decisionTools)}
        <section class="idea-expansion-actions" aria-label="Explore more ideas">
          {#if canRequestBatch || batchUsageKnown}
            <div class="idea-expansion-row">
              <div>
                <strong>{batchLimitReached ? "Idea batch limit reached" : "Want a broader pool?"}</strong>
                <span>Append a fresh batch. Existing candidate scores and your shortlist stay unchanged; the ranked list may reorder around new arrivals.</span>
                {#if batchUsageKnown}
                  <small class="idea-batch-usage">{completedBatchCount} of {batchMaximum} additional batches used</small>
                {/if}
              </div>
              <button
                type="button"
                disabled={poolMutationBusy || !canRequestBatch}
                onclick={() => {
                  regenerateError = "";
                  regenerateOverlayOpen = true;
                }}
              >
                Add another batch
              </button>
            </div>
          {/if}
          {#if decisionTools}
            <div class="idea-expansion-row">
              <div>
                <strong>Have a specific direction in mind?</strong>
                <span>Branch from one or two promising candidates, then evaluate only the direction you choose.</span>
              </div>
              <button
                type="button"
                disabled={poolMutationBusy}
                onclick={() => {
                  void goto(selectionWorkspaceHref("compare", { tool: "variants" }), {
                    state: jobPageToolState(),
                  });
                }}
              >
                {BRANCH_DIRECTION_LABEL}
              </button>
            </div>
          {/if}
        </section>
      {/if}
    </div>

    {#if interactive}
      <div class="decision-rail-wrap">
        {#if selectionJourney}
          <DecisionRail
            journey={selectionJourney}
            deepResearchCost={deepCost}
            busy={poolMutationBusy || selectLoading || shortlistSaveState === "saving"}
            busyReason={shortlistSaveState === "saving"
              ? "Wait for the shortlist to finish saving."
              : poolMutationBusy
                ? "Another idea update is running. You can review the research scope when it finishes."
                : "Opening the research scope…"}
            saveState={shortlistSaveState}
            saveError={shortlistSaveError}
            saveConflict={shortlistSaveConflict}
            onRemoveShortlistItem={(ideaId, ideaRevision) => toggle(`${ideaId}:${ideaRevision}`)}
            onRetrySave={retryShortlistSave}
            onReloadSave={reloadShortlist}
            onStartDeepResearch={handleValidate}
          />
        {:else}
          <aside class="decision-rail-fallback" aria-live="polite">
            <p class="decision-rail-fallback__eyebrow">Research shortlist</p>
            <h3>{selectionCount} of {MAX_SELECTIONS} ideas selected</h3>
            {#if selectionDecisionStateLoading}
              <p>Loading your next step…</p>
            {:else if selectionDecisionStateError}
              <p>{selectionDecisionStateError}</p>
              <button type="button" class="decision-rail-retry" onclick={() => { void loadSelectionDecisionState(); }}>
                Try again
              </button>
            {:else}
              <p>Select one to three ideas to define what Deep Research should cover.</p>
            {/if}
            <button
              type="button"
              class="decision-rail-start"
              disabled={!canSubmit || poolMutationBusy || selectLoading || shortlistSaveState === "saving"}
              onclick={handleValidate}
            >
              Review scope
            </button>
          </aside>
        {/if}
      </div>
    {/if}
  </div>

  {#snippet variantNotesBlock()}
    <div class="variant-notes">
      {#each rejectedOverlapGroups as g}
        <article class="variant-note">
          <div class="variant-note-copy">
            <span class="variant-note-kicker">Similar idea family · {g.ideaNames.length}</span>
            <strong>{g.sharedProduct || "Same buyer job"}</strong>
            <div class="variant-note-names" aria-label="Ideas in this family">
              {#each g.ideaNames as name}<span>{name}</span>{/each}
            </div>
          </div>
          {#if interactive && g.comparisonIdeas.length > 0}
            <button type="button" class="variant-note-action" onclick={() => openOverlapComparison(g)}>
              Compare variants
            </button>
          {:else if interactive}
            <span class="variant-note-hint">Shortlist 2-3 to compare</span>
          {/if}
        </article>
      {/each}
    </div>
  {/snippet}

  {#snippet ruledOutBlock()}
    <RuledOutList
      findings={examinedRuledOut ?? []}
      highlightedIndex={seedHighlightRuledOutIndex}
      onOpen={openRuledOutDetail}
    />
  {/snippet}

  {#if interactive}
    <!-- Secondary context stays below the decision surface: saved build limits,
         portfolio shape, and the collapsed Discovery appendix. -->
    <!-- Build limits are a decision tool. The profile itself rides the job payload and
         is never blanked, so a revoked grant would otherwise still show the saved
         summary and an Edit button whose save 403s. -->
    {#if decisionTools}
      <DecisionBrief
        bind:this={decisionBriefRef}
        {jobId}
        profile={activeDecisionProfile}
        variant={briefVariant}
        onSaved={handleDecisionProfileSaved}
      />
    {/if}

    {#if shape}
      <p class="shape-note">{shape.line}</p>
    {/if}

    {#if appendixHasContent}
      <AnalysisAppendix meta={appendixMeta} bind:expanded={appendixExpanded}>
        {#if summarySupportingNotes.length}
          <section class="appendix-notes" aria-label="Analyst notes">
            <header class="appendix-notes-heading">
              <span>Analyst synthesis</span>
              <h3>What shaped the shortlist</h3>
            </header>
            <ol class="appendix-note-list">
              {#each summarySupportingNotes as note, index}
                <li class="appendix-note">
                  <span class="appendix-note-index">{String(index + 1).padStart(2, "0")}</span>
                  <p>
                    <IdeaReferenceText content={note} references={ideaReferences} onOpen={openIdeaReference} />
                  </p>
                </li>
              {/each}
            </ol>
          </section>
        {/if}
        {#if collaboratorFeedbackGroups.length > 0}
          <CollaboratorFeedback
            groups={collaboratorFeedbackGroups}
            onOpen={openDetailByKey}
            onAskAnalyst={askAnalystAboutCollaboratorFeedback}
          />
        {/if}
        {#if rejectedOverlapGroups.length > 0}
          {@render variantNotesBlock()}
        {/if}
        {#if examinedRuledOut && examinedRuledOut.length > 0}
          {@render ruledOutBlock()}
        {/if}
        {#if hasCoverageDisclosures}
          <ResearchContextNotes
            shapeLine={null}
            coverageNotes={coverageNotes ?? []}
            userAdjustments={userAdjustments ?? []}
            {marketReality}
          />
        {/if}
      </AnalysisAppendix>
    {/if}
  {:else}
    <!-- Visitor (shared) view: original inline rendering, unchanged by Phase 1b. -->
    {#if shape || hasCoverageDisclosures}
      <ResearchContextNotes
        shapeLine={shape?.line}
        coverageNotes={coverageNotes ?? []}
        userAdjustments={userAdjustments ?? []}
        {marketReality}
      />
    {/if}

    {#if summaryParagraphs.length}
      <AnalystRecommendation
        recommendation={summaryRecommendation}
        supportingNotes={summarySupportingNotes}
        references={ideaReferences}
        onOpen={openIdeaReference}
      />
    {/if}

    {#if rejectedOverlapGroups.length > 0}
      {@render variantNotesBlock()}
    {/if}

    {#if examinedRuledOut && examinedRuledOut.length > 0}
      {@render ruledOutBlock()}
    {/if}
  {/if}

</div>

</div>

<!-- ═══ Analyst window (G3 — chatMode-independent; never in the visitor view) ═══
     An OVERLAY, not a column: the candidate table keeps the whole page, and the
     analyst floats over the corner of it — the messenger idiom, which is what a
     companion that you consult while working actually is. Expanding centres it at
     reading width; closing leaves a single launcher pill. -->
{#if interactive}
  <WorkspaceOverlay
    open={chatPanel.isOpen}
    modal={chatPanel.isExpanded}
    label="Analyst conversation"
    onClose={closeChatOverlay}
  >
      <ChatThread
        bind:this={chatThreadRef}
        bind:weakPool
        {jobId}
        dock="rail"
        currentIdeaFocus={regenerateFocus}
        applying={poolMutationBusy}
        blocked={poolMutationBusy}
        onApplyPatch={handleApplyPatch}
        onCopilotAction={handleCopilotAction}
        {seedCost}
        onSeedSubmit={(patch, sourceMessageId) => { void handleSeed(patch, sourceMessageId); }}
        onReviewVariant={handleReviewVariant}
        onUseVariant={handleUseVariant}
        starters={chatSuggestions}
        starterPrompt={analystStarterPrompt}
        selectionContext={analystSelectionContext}
        onStarterConsumed={() => { analystStarterPrompt = null; }}
        {ideaReferences}
        onOpenIdeaReference={openChatIdeaReference}
        focused={chatPanel.isExpanded}
        onToggleFocus={() => chatPanel.toggleExpanded()}
        onCollapse={() => {
          restoreFocusToLauncher = true;
          chatPanel.close();
        }}
      />
  </WorkspaceOverlay>

  {#if !chatPanel.isOpen}
    <button
      type="button"
      class="chat-launcher"
      bind:this={launcherEl}
      aria-haspopup="dialog"
      onclick={() => chatPanel.open()}
    >
      <MessageSquare class="w-4 h-4" aria-hidden="true" />
      {analystLauncherLabel}
    </button>
  {/if}
{/if}

{#if interactive}
  {#snippet regenerateFooter()}
    <button
      type="button"
      class="copilot-shortlist-cancel"
      disabled={regenerating || isRegenerating}
      onclick={() => (regenerateOverlayOpen = false)}
    >
      Cancel
    </button>
    <button
      type="button"
      class="copilot-shortlist-apply"
      disabled={poolMutationBusy || !canRequestBatch || !canAffordRegenerate}
      onclick={() => void handleRegenerate()}
    >
      {#if regenerating || isRegenerating}
        <Loader2 class="w-4 h-4 animate-spin" aria-hidden="true" />
        Adding batch…
      {:else}
        {generateNewBatchLabel(regenerateCost)}
      {/if}
    </button>
  {/snippet}
  <FormOverlay
    open={regenerateOverlayOpen}
    size="compact"
    eyebrow="Fresh idea batch"
    title="Add another batch"
    description="Append a small set of ideas for review. Existing candidate scores and your shortlist stay unchanged; the list may reorder around new arrivals."
    onRequestClose={() => {
      if (!regenerating && !isRegenerating) regenerateOverlayOpen = false;
    }}
    footer={regenerateFooter}
  >
    <div class="regenerate-form">
      <div class="regen-focus" role="group" aria-label="Idea focus for the next batch">
        {#each REGEN_FOCUSES as focus}
          <button
            type="button"
            onclick={() => (regenerateFocus = focus.value)}
            disabled={poolMutationBusy}
            class="regen-focus-btn"
            class:is-active={regenerateFocus === focus.value}
            aria-pressed={regenerateFocus === focus.value}
          >
            {focus.label}
          </button>
        {/each}
      </div>
      <p class="regenerate-help">
        {#if regenerateFocus === "novelty"}
          Look for a different buyer, workflow, or product mechanism.
        {:else if regenerateFocus === "distribution"}
          Favor ideas with a clearer path to customers you can reach.
        {:else}
          Use the strongest gaps in this research to choose the next angle.
        {/if}
      </p>
      {#if !canAffordRegenerate}
        <p class="copilot-shortlist-error" role="alert">
          You need {regenerateCost} credits to generate this batch. Your current ideas are unchanged.
        </p>
      {/if}
      {#if regenerateError}
        <p class="copilot-shortlist-error" role="alert">{regenerateError}</p>
      {/if}
    </div>
  </FormOverlay>

  {#snippet copilotShortlistFooter()}
    <button
      type="button"
      class="copilot-shortlist-cancel"
      onclick={() => { copilotShortlistReview = null; copilotShortlistError = ""; }}
    >
      Keep current shortlist
    </button>
    <button
      type="button"
      class="copilot-shortlist-apply"
      disabled={shortlistSaveRunning}
      onclick={applyCopilotShortlist}
    >
      Apply shortlist
    </button>
  {/snippet}
  <FormOverlay
    open={Boolean(copilotShortlistReview)}
    eyebrow={copilotShortlistReview?.source === "comparison" ? "Comparison handoff" : "Analyst suggestion"}
    title="Review shortlist changes"
    description="Nothing changes until you apply this exact set. Saving uses the current shortlist version."
    onRequestClose={() => { copilotShortlistReview = null; copilotShortlistError = ""; }}
    footer={copilotShortlistFooter}
  >
    <div class="copilot-shortlist-review">
      <section>
        <p class="copilot-shortlist-label">Current shortlist</p>
        {#if selectedIdeas.length > 0}
          <ol>
            {#each selectedIdeas as idea}
              <li>{solutionDisplayTitle(idea)}</li>
            {/each}
          </ol>
        {:else}
          <p class="copilot-shortlist-empty">No ideas selected.</p>
        {/if}
      </section>
      <section class="copilot-shortlist-proposed">
          <p class="copilot-shortlist-label">
            {copilotShortlistReview?.source === "comparison" ? "Proposed shortlist" : "Suggested shortlist"}
          </p>
        <ol>
          {#each copilotShortlistReview?.ideas ?? [] as idea}
            <li>{solutionDisplayTitle(idea)}</li>
          {/each}
        </ol>
      </section>
      {#if copilotShortlistReview?.rationale}
        <div class="copilot-shortlist-rationale">
          <p class="copilot-shortlist-label">
            {copilotShortlistReview?.source === "comparison" ? "Why this handoff opened" : "Why the analyst suggested it"}
          </p>
          <p>{copilotShortlistReview.rationale}</p>
        </div>
      {/if}
      {#if copilotShortlistError}
        <p class="copilot-shortlist-error" role="alert">{copilotShortlistError}</p>
      {/if}
    </div>
  </FormOverlay>

{/if}

<!-- Detail modal -->
{#if modalIndex !== null && sortedSolutions[modalIndex]}
  {@const detailIndex = modalIndex}
  {#if interactive}
    <SolutionDetail
      open={modalIndex !== null}
      solution={sortedSolutions[modalIndex]}
      solutions={sortedSolutions}
      currentIndex={modalIndex}
      {jobId}
      lifecycle="selection"
      activeTab={detailTab}
      evidenceLinks={detailEvidenceLinks}
      overlapGroups={overlapGroups ?? []}
      isSelected={selectedIdeaKeys.has(ideaKey(sortedSolutions[modalIndex]))}
      selectionIndex={selectionIndexOf(ideaKey(sortedSolutions[modalIndex]))}
      selectedCount={selectionCount}
      maxSelections={MAX_SELECTIONS}
      maxReached={selectedIdeaKeys.size >= MAX_SELECTIONS}
      disabled={selectLoading || poolMutationBusy}
      disabledReason={selectLoading
        ? "Saving your shortlist…"
        : poolMutationBusy
          ? "Another idea update is running. You can change the shortlist when it finishes."
          : undefined}
      onSelect={handleToggleAdapter}
      onOpenEvidence={handleOpenDetailEvidence}
      onTabChange={handleDetailTabChange}
      onNavigate={handleNavigate}
      onClose={handleCloseDetail}
      voteCount={voteCountFor(sortedSolutions[detailIndex])}
    />
  {:else}
    {#snippet detailAction()}
      {#if actionSlot}
        {@render actionSlot({ solution: sortedSolutions[detailIndex], index: detailIndex })}
      {/if}
    {/snippet}
    <SolutionDetail
      open={modalIndex !== null}
      solution={sortedSolutions[modalIndex]}
      solutions={sortedSolutions}
      currentIndex={modalIndex}
      lifecycle="reference"
      activeTab={detailTab}
      evidenceLinks={detailEvidenceLinks}
      overlapGroups={overlapGroups ?? []}
      onOpenEvidence={handleOpenDetailEvidence}
      onTabChange={handleDetailTabChange}
      onNavigate={handleNavigate}
      onClose={handleCloseDetail}
      actionSlot={detailAction}
      voteCount={voteCountFor(sortedSolutions[detailIndex])}
    />
  {/if}
{/if}

{#if ruledOutDetail}
  <RuledOutDetail finding={ruledOutDetail} onClose={handleCloseRuledOutDetail} />
{/if}

<style>
  /* The candidate table owns the page — the analyst is an OVERLAY, never a column
     and never a slab in the flow. (Two earlier attempts: a 20rem grid rail crushed
     the analyst's prose to ~35 CPL; a wider track just moved the crushing onto the
     table, then stacked a wall of chat into the page below 1440px.) */
  .workbench-shell {
    display: block;
    padding-bottom: calc(var(--decision-rail-height, var(--space-20)) + var(--space-4));
  }

  /* ── Launcher: the one way back in, always the same corner ── */
  .chat-launcher {
    position: fixed;
    right: clamp(0.75rem, 2vw, 1.5rem);
    /* Track the dock's measured height rather than guessing it.
       --decision-rail-height is published by DecisionRail; the constant stays as
       the fallback for surfaces that render no dock. */
    bottom: calc(var(--decision-rail-height, var(--space-16)) + var(--space-4));
    z-index: var(--z-overlay, 30);
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    min-height: 2.75rem;
    padding: 0.6rem 1rem;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border-emphasis);
    border-radius: var(--radius-full);
    box-shadow: var(--shadow-md);
    color: var(--color-text-primary);
    font-family: var(--font-body);
    font-size: var(--text-13);
    font-weight: 700;
    cursor: pointer;
    transition: border-color var(--duration-fast) var(--ease-default), box-shadow var(--duration-fast) var(--ease-default),
      transform var(--duration-fast) var(--ease-default);
  }
  .chat-launcher:hover {
    border-color: var(--color-accent);
  }
  .chat-launcher:active {
    transform: scale(0.98);
  }
  .chat-launcher:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  /* A modal form makes every sibling inert. Leaving the analyst visibly above
     that form created a dead-looking pane: present but impossible to use.
     Preserve its store/draft while hiding the frame; closing the form reveals
     the same docked/expanded state and FormOverlay restores focus. */
  :global(body:has([data-form-overlay="true"]) .workspace-overlay:has(.workspace-overlay__frame[aria-label="Analyst conversation"])) {
    visibility: hidden;
    pointer-events: none;
  }

  @media (prefers-reduced-motion: reduce) {
    .chat-launcher { transition: none; }
    .chat-launcher:active { transform: none; }
  }

  .workbench {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    padding: var(--space-4);
    background:
      var(--color-bg-elevated);
    /* Card chrome = 1px border + shadow-sm only (Phase-1b bevel fix; slop
       guardrail 11 — no white-mix sheen/bevel shadows). */
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 52%, transparent);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
  }
  .selection-layout {
    display: block;
  }
  .candidate-pool {
    min-width: 0;
  }
  .decision-rail-wrap {
    position: static;
    min-width: 0;
  }
  .decision-rail-fallback {
    display: grid;
    gap: 0.75rem;
    padding: 1.25rem;
    border: 1px solid var(--color-border-emphasis);
    border-radius: var(--radius-lg);
    background: var(--color-bg-elevated);
    box-shadow: var(--shadow-sm);
  }
  .decision-rail-fallback__eyebrow {
    margin: 0;
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }
  .decision-rail-fallback h3,
  .decision-rail-fallback p {
    margin: 0;
  }
  .decision-rail-fallback p {
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: 1.5;
  }
  .decision-rail-retry,
  .decision-rail-start {
    min-height: 2.75rem;
    padding: 0.65rem 0.9rem;
    border-radius: var(--radius-md);
    font: inherit;
    font-size: var(--text-sm);
    font-weight: 700;
    cursor: pointer;
  }
  .decision-rail-retry {
    border: 1px solid var(--color-border-emphasis);
    color: var(--color-text-primary);
    background: var(--color-bg-elevated);
  }
  .decision-rail-start {
    border: 0;
    color: var(--color-text-on-accent);
    background: var(--color-accent-hover);
  }
  .decision-rail-retry:hover { border-color: var(--color-input-border-hover); background: var(--color-bg-surface); }
  .decision-rail-start:hover:not(:disabled) { background: var(--color-accent-dark); }
  .decision-rail-retry:active, .decision-rail-start:active:not(:disabled) { transform: scale(0.98); }
  .decision-rail-start:disabled {
    color: var(--color-text-muted);
    background: var(--color-bg-hover);
    cursor: not-allowed;
  }
  @media (prefers-reduced-motion: reduce) {
    .decision-rail-retry, .decision-rail-start { transition: none; }
    .decision-rail-retry:active, .decision-rail-start:active { transform: none; }
  }
  .workbench-anchor {
    position: absolute;
    top: -5.5rem;
    left: 0;
    width: 1px;
    height: 1px;
    pointer-events: none;
  }

  /* ── Command header ── */
  .cmd {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(12rem, 15rem);
    align-items: center;
    gap: 1rem;
    padding: 0 0.1rem 0.72rem;
    background: transparent;
    border: 0;
    border-bottom: 1px solid color-mix(in srgb, var(--color-border-emphasis) 42%, transparent);
    border-radius: var(--radius-none);
  }
  .cmd.cmd-owner { grid-template-columns: minmax(0, 1fr); }
  .cmd-title {
    margin: 0;
    max-width: 42ch;
    font-family: var(--font-display);
    font-size: 1.375rem;
    font-weight: 700;
    line-height: 1.15;
    letter-spacing: -0.02em;
    color: var(--color-text-primary);
    text-wrap: balance;
  }
  .cmd-sub {
    margin: 0.14rem 0 0;
    max-width: 68ch;
    font-size: var(--text-sm);
    line-height: 1.48;
    color: var(--color-text-secondary);
    text-wrap: pretty;
  }
  /* Stats fold into the title row as ONE record line (global .record-line
     utility carries the mono treatment) — never a boxed stat-cell strip. */
  .cmd-title-row {
    display: flex;
    align-items: baseline;
    gap: 1rem;
    flex-wrap: wrap;
  }
  .cmd-stats {
    margin: 0;
  }
  /* Inherits the record line's mono/uppercase treatment so the tally reads as part of
     the stat run, not a button parked in it — only the underline marks it as openable. */
  .cmd-stats-link {
    padding: 0;
    border: 0;
    background: none;
    color: var(--color-accent-dark);
    font: inherit;
    letter-spacing: inherit;
    text-transform: inherit;
    text-decoration: underline;
    text-underline-offset: 0.25em;
    cursor: pointer;
  }
  .cmd-stats-link:hover { color: var(--color-text-primary); }
  .cmd-stats-link:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .cmd-status {
    display: grid;
    gap: 0.3rem;
    align-self: start;
    justify-self: end;
    width: 100%;
    padding: 0.06rem 0 0.06rem 0.95rem;
    border-left: 1px solid var(--color-border);
    color: var(--color-text-muted);
  }
  .cmd-status p {
    margin: 0;
    font-size: var(--text-11);
    line-height: 1.32;
    text-align: right;
    color: var(--color-text-muted);
  }
  /* visitor-mode vote tally (replaces the selection status) */
  .cmd-status--votes {
    gap: 0.34rem;
    align-content: start;
  }
  .vote-tally {
    display: flex;
    align-items: baseline;
    justify-content: flex-end;
    gap: 0.42rem;
  }
  .vote-tally-num {
    font-family: var(--font-mono);
    font-size: var(--text-2xl);
    font-weight: 800;
    line-height: 1;
    color: var(--color-text-primary);
    font-variant-numeric: tabular-nums;
  }
  .vote-tally-label {
    font-size: var(--text-11);
    font-weight: 700;
    color: var(--color-text-muted);
  }
  .vote-tally-hint {
    margin: 0;
    max-width: 13rem;
    justify-self: end;
    font-size: var(--text-sm);
    line-height: 1.4;
    color: var(--color-text-muted);
    text-align: right;
    text-wrap: pretty;
  }

  .regenerate-form {
    display: grid;
    gap: 0.85rem;
  }
  .regen-focus {
    display: inline-flex;
    justify-self: start;
    gap: 0.18rem;
    padding: 0.18rem;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
  }
  .regen-focus-btn {
    min-height: 2.5rem;
    padding: 0.32rem 0.55rem;
    background: transparent;
    border: 1px solid transparent;
    border-radius: var(--radius-sm);
    color: var(--color-text-secondary);
    font-family: var(--font-body);
    font-size: var(--text-sm);
    font-weight: 700;
    cursor: pointer;
    transition:
      transform var(--duration-fast) var(--ease-default),
      border-color var(--duration-fast) var(--ease-default),
      color var(--duration-fast) var(--ease-default),
      background var(--duration-fast) var(--ease-default);
  }
  .regen-focus-btn:hover:not(:disabled) {    color: var(--color-text-secondary);
  }
  .regen-focus-btn.is-active {
    background: var(--color-bg-elevated);
    border-color: color-mix(in srgb, var(--color-accent) 24%, transparent);
    color: var(--color-accent-dark);
  }
  .regen-focus-btn:disabled {
    background: var(--color-bg-hover);
    color: var(--color-text-muted);
    cursor: not-allowed;
  }
  @media (prefers-reduced-motion: reduce) {
    .regen-focus-btn { transition: none; }
  }
  .regenerate-help {
    margin: 0;
    color: var(--color-text-secondary);
    font-size: var(--text-base);
    line-height: 1.5;
    text-wrap: pretty;
  }
  /* ── Decision home: one recommendation, three lightweight checks ── */
  .decision-guide {
    display: grid;
    grid-template-columns: minmax(16rem, 0.8fr) minmax(28rem, 1.2fr);
    gap: var(--space-6);
    align-items: center;
    margin-bottom: var(--space-3);
    padding: var(--space-4);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-bg-surface);
  }

  .decision-guide__copy {
    display: grid;
    gap: var(--space-1);
  }

  .decision-guide__eyebrow,
  .discovery-take__eyebrow {
    margin: 0;
    /* -secondary, not -muted: 10-11px mono caps on bg-surface needs more than
       muted's 4.32:1. */
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .decision-guide__copy h3,
  .decision-guide__copy p {
    margin: 0;
  }

  .decision-guide__copy h3 {
    color: var(--color-text-primary);
    font-family: var(--font-display);
    font-size: var(--text-lg);
    font-weight: 700;
    line-height: 1.25;
  }

  .decision-guide__copy > p:last-of-type {
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: 1.5;
  }

  .decision-guide__candidate {
    justify-self: start;
    min-height: 2.5rem;
    margin-top: var(--space-2);
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--color-border-emphasis);
    border-radius: var(--radius-md);
    background: var(--color-bg-elevated);
    color: var(--color-text-primary);
    font: inherit;
    font-size: var(--text-sm);
    font-weight: 700;
    cursor: pointer;
    transition: border-color var(--duration-fast) var(--ease-default), background var(--duration-fast) var(--ease-default), transform var(--duration-fast) var(--ease-default);
  }

  /* Read-only progress list (no navigation): status per optional check. */
  .decision-guide__progress {
    display: grid;
    gap: var(--space-2);
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .decision-guide__progress-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    min-width: 0;
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-bg-elevated);
  }

  .decision-guide__progress-name {
    min-width: 0;
    overflow: hidden;
    color: var(--color-text-primary);
    font-size: var(--text-sm);
    font-weight: 700;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .decision-guide__candidate:hover:not(:disabled) {
    border-color: var(--color-input-border-hover);
    background: var(--color-bg-hover);
  }

  .decision-guide__candidate:active:not(:disabled),
  .idea-expansion-row button:active:not(:disabled) {
    transform: scale(0.98);
  }

  .decision-guide__candidate:disabled,
  .idea-expansion-row button:disabled {
    color: var(--color-text-muted);
    background: var(--color-bg-hover);
    cursor: not-allowed;
  }

  .discovery-take {
    display: grid;
    gap: var(--space-2);
    margin-bottom: var(--space-4);
    padding: var(--space-3) var(--space-4);
    border-top: 1px solid var(--color-border);
    border-bottom: 1px solid var(--color-border);
  }

  .discovery-take__quote {
    max-width: 74ch;
    margin: 0;
    color: var(--color-text-primary);
    font-family: var(--font-display);
    font-size: var(--text-md);
    font-weight: 600;
    line-height: 1.45;
    letter-spacing: -0.01em;
    text-wrap: pretty;
  }
  .discovery-take__quote :global(button.idea-reference-link) {
    color: inherit;
    font: inherit;
    text-decoration-color: var(--color-border-emphasis);
    text-decoration-line: underline;
    text-decoration-style: dotted;
    text-decoration-thickness: 1px;
    text-underline-offset: 0.18em;
    transition: color var(--duration-fast) var(--ease-default), text-decoration-color var(--duration-fast) var(--ease-default);
  }
  .discovery-take__quote :global(button.idea-reference-link:hover) {
    color: var(--color-accent-dark);
    text-decoration-color: currentColor;
  }
  .shape-note {
    max-width: 74ch;
    margin: 0;
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: 1.5;
  }

  .idea-expansion-actions {
    display: grid;
    margin-top: var(--space-3);
    padding: 0 var(--space-4);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-bg-surface);
  }

  .idea-expansion-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-4);
    padding: var(--space-3) 0;
    border-top: 1px solid var(--color-border);
  }
  .idea-expansion-row:first-child { border-top: 0; }

  .idea-expansion-row > div {
    display: grid;
    gap: var(--space-1);
  }

  .idea-expansion-row strong {
    font-size: var(--text-sm);
    font-weight: 700;
  }

  .idea-expansion-row span {
    color: var(--color-text-secondary);
    font-size: var(--text-xs);
    line-height: var(--leading-normal);
  }

  .idea-expansion-row .idea-batch-usage {
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-variant-numeric: tabular-nums;
  }

  .idea-expansion-row button {
    flex: 0 0 auto;
    min-height: 2.5rem;
    padding: var(--space-2) var(--space-3);
    border: 0;
    border-radius: var(--radius-md);
    background: transparent;
    color: var(--color-accent-dark);
    font: inherit;
    font-size: var(--text-sm);
    font-weight: 700;
    cursor: pointer;
    transition: color var(--duration-fast) var(--ease-default), background var(--duration-fast) var(--ease-default), transform var(--duration-fast) var(--ease-default);
  }

  .idea-expansion-row button:hover:not(:disabled) {
    background: var(--color-accent-subtle);
  }

  @media (prefers-reduced-motion: reduce) {
    .decision-guide__candidate,
    .idea-expansion-row button {
      transition: none;
    }
    .decision-guide__candidate:active,
    .idea-expansion-row button:active {
      transform: none;
    }
  }

  /* ── Appendix: analyst supporting notes ── */
  .appendix-notes {
    display: grid;
    gap: var(--space-4);
  }
  .appendix-notes-heading {
    display: grid;
    gap: var(--space-1);
  }
  .appendix-notes-heading span {
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: var(--tracking-wide);
    text-transform: uppercase;
  }
  .appendix-notes-heading h3 {
    margin: 0;
    color: var(--color-text-primary);
    font-family: var(--font-display);
    font-size: var(--text-xl);
    font-weight: 700;
    line-height: var(--leading-tight);
  }
  .appendix-note-list {
    display: grid;
    margin: 0;
    padding: 0;
    border-top: 1px solid var(--color-border);
    border-bottom: 1px solid var(--color-border);
    list-style: none;
  }
  .appendix-note {
    display: grid;
    grid-template-columns: var(--space-8) minmax(0, 1fr);
    gap: var(--space-4);
    padding: var(--space-4) 0;
    border-top: 1px solid var(--color-border);
  }
  .appendix-note:first-child {
    border-top: 0;
  }
  .appendix-note-index {
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }
  .appendix-note p {
    max-width: 76ch;
    margin: 0;
    color: var(--color-text-secondary);
    font-size: var(--text-base);
    line-height: var(--leading-relaxed);
    text-wrap: pretty;
  }
  .appendix-note p :global(button.idea-reference-link) {
    color: inherit;
    font-weight: 600;
    text-decoration-color: var(--color-border-emphasis);
    text-decoration-line: underline;
    text-decoration-style: dotted;
    text-decoration-thickness: 1px;
    text-underline-offset: var(--space-1);
    transition: color var(--duration-fast) var(--ease-default), text-decoration-color var(--duration-fast) var(--ease-default);
  }
  .appendix-note p :global(button.idea-reference-link:hover) {
    color: var(--color-accent-dark);
    text-decoration-color: currentColor;
  }

  @media (max-width: 760px) {
    .appendix-note {
      grid-template-columns: var(--space-6) minmax(0, 1fr);
      gap: var(--space-3);
    }
  }

  .regen-error {
    margin: 0;
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--color-error-text);
    text-align: right;
  }

  .detail-link-error {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    padding: var(--space-3);
    border: 1px solid color-mix(in srgb, var(--color-warning) 35%, var(--color-border));
    border-radius: var(--radius-md);
    background: var(--color-warning-subtle);
    color: var(--color-warning-text);
  }

  .detail-link-error p {
    margin: 0;
    min-width: 0;
    font-size: var(--text-sm);
    line-height: 1.5;
    overflow-wrap: anywhere;
  }

  .detail-link-error button {
    min-height: 2rem;
    flex-shrink: 0;
    padding: 0 var(--space-3);
    border: 1px solid color-mix(in srgb, var(--color-warning) 35%, var(--color-border));
    border-radius: var(--radius-sm);
    background: var(--color-bg-elevated);
    color: var(--color-text-primary);
    font: inherit;
    font-size: var(--text-sm);
    font-weight: 700;
    cursor: pointer;
  }

  .detail-link-error button:hover {
    border-color: var(--color-border-emphasis);
  }

  .detail-link-error button:active {
    transform: scale(0.97);
  }

  @media (prefers-reduced-motion: reduce) {
    .detail-link-error button:active {
      transform: none;
    }
  }

  /* Idea-seed settlement banner — points at the row/panel entry the reconcile
     effect just scrolled to and highlighted, rather than leaving the outcome
     only visible back in the (possibly docked/collapsed) analyst window. */
  .seed-banner {
    margin: 0;
    padding: 0.5rem 0.7rem;
    border: 1px solid var(--color-border-emphasis);
    border-radius: var(--radius-md);
    background: var(--color-bg-surface);
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    line-height: 1.4;
  }
  .seed-banner--accepted {
    border-color: color-mix(in srgb, var(--color-success) 30%, transparent);
    background: color-mix(in srgb, var(--color-success) 6%, var(--color-bg-surface));
    color: var(--color-success-text);
  }

  /* Momentary landing highlight for a settled seed — the row it scrolls to. */
  .row-seed-highlight,
  .row-batch-highlight {
    animation: seed-row-flash var(--duration-slowest) var(--ease-out);
  }
  @keyframes seed-row-flash {
    0%, 15% { background: color-mix(in srgb, var(--color-accent) 14%, transparent); }
    100% { background: transparent; }
  }
  @media (prefers-reduced-motion: reduce) {
    .row-seed-highlight { animation: none; }
  }

  .cell-metric-head:focus-visible,
  .regen-focus-btn:focus-visible,
  .variant-note-action:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  /* ── Opportunity list ── */
  .opp-list {
    display: grid;
    gap: 0;
    overflow: hidden;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
  }
  .shortlist-overlap-notice {
    display: grid;
    gap: var(--space-1);
    margin-bottom: var(--space-3);
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-bg-surface);
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: 1.45;
  }
  .shortlist-overlap-notice p {
    margin: 0;
  }
  /* Metric tracks are sized for the widest UPPERCASE label plus the sort arrow,
     which is always laid out (hidden when the column is idle) so activating a
     sort never steals width from the label. FEASIBILITY (11 mono caps, no space
     to wrap on) is the binding constraint. */
  .opp-row {
    display: grid;
    grid-template-columns: 1.35rem 5.65rem minmax(0, 1fr) 5.5rem 5.5rem 5.8rem 5.5rem;
    align-items: center;
    gap: 0.56rem;
    padding: 0.56rem 0.68rem;
    border: 0;
    border-top: 1px solid var(--color-border);
    border-radius: var(--radius-none);
    background: var(--color-bg-elevated);
    box-shadow: none;
    transition:
      background var(--duration-fast) var(--ease-default),
      box-shadow var(--duration-fast) var(--ease-default);
  }
  .opp-row-head {
    min-height: 1.75rem;
    padding: 0.4rem 0.7rem;
    border: 0;
    border-bottom: 1px solid color-mix(in srgb, var(--color-border-emphasis) 42%, transparent);
    border-radius: var(--radius-none);
    background: color-mix(in srgb, var(--color-bg-surface) 74%, var(--color-bg-elevated));
    box-shadow: none;
  }
  .opp-row:not(.opp-row-head):hover {
    background: color-mix(in srgb, var(--color-bg-surface) 48%, var(--color-bg-elevated));
  }
  .opp-row-sel {
    background: var(--color-accent-subtle);
  }
  .opp-row-maxed { opacity: 1; }

  /* Role-only wrapper: carries columnheader/rowheader semantics for an
     interactive cell without introducing a box, so the button underneath
     stays a direct grid item of .opp-row. */
  .cell-shell {
    display: contents;
  }
  .cell-metric-shell {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 0.1rem;
    align-items: center;
    min-width: 0;
  }
  .cell-metric-shell :global(.metric-help.tooltip-wrapper) {
    min-width: 1.75rem;
    min-height: 2.5rem;
  }

  .cell-rank {
    font-family: var(--font-mono);
    font-size: var(--text-13);
    font-weight: 700;
    color: var(--color-text-secondary);
    font-variant-numeric: tabular-nums;
    text-align: center;
  }
  /* Mono uppercase header, matching the dashboard list-head "hardware" label. */
  .opp-row-head .cell-rank,
  .opp-row-head .cell-select-label,
  .opp-row-head .cell-title-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    line-height: 1;
    color: var(--color-text-secondary);
  }
  .opp-row-head .cell-title-label { padding-left: 0; }

  /* select control */
  .cell-select-label {
    text-align: center;
  }
  /* visitor-mode action cell (vote button rendered via actionSlot) */
  .cell-action {
    display: flex;
    justify-content: center;
    min-width: 0;
  }
  .select-control {
    position: relative;
    justify-self: center;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.34rem;
    width: 100%;
    min-height: 2rem;
    padding: 0 0.44rem;
    border-radius: var(--radius-sm);
    border: 1px solid var(--color-input-border);
    background: var(--color-bg-elevated);
    color: var(--color-text-muted);
    cursor: pointer;
    font-family: var(--font-body);
    font-size: var(--text-11);
    font-weight: 700;
    transition:
      transform var(--duration-fast) var(--ease-default),
      border-color var(--duration-fast) var(--ease-default),
      background var(--duration-fast) var(--ease-default),
      color var(--duration-fast) var(--ease-default);
  }
  /* Hover is a neutral control hover (§8) — it must never wear accent, or an
     un-picked row under the cursor reads as picked. Accent belongs to .sel only. */
  .select-control:hover:not(.maxed) {
    border-color: var(--color-input-border-hover);
    color: var(--color-text-primary);
    background: var(--color-bg-surface);
  }
  .select-control.sel {
    border-color: var(--color-accent);
    background: color-mix(in srgb, var(--color-accent) 7%, var(--color-bg-elevated));
    color: var(--color-accent-dark);
    box-shadow: none;
  }
  .select-control.sel .select-marker {
    border-color: var(--color-accent);
    background: var(--color-accent-dark);
    color: var(--color-text-on-accent);
  }
  .select-control.maxed {
    border-color: var(--color-border);
    color: var(--color-text-secondary);
    cursor: not-allowed;
  }
  .select-control:active:not(.maxed) { transform: scale(0.96); }
  @media (prefers-reduced-motion: reduce) {
    .select-control { transition: none; }
    .select-control:active:not(.maxed) { transform: none; }
  }
  .select-marker {
    display: grid;
    place-items: center;
    width: var(--space-4);
    height: var(--space-4);
    border-radius: var(--radius-sm);
    border: 1px solid currentColor;
    flex-shrink: 0;
  }
  .select-copy {
    position: static;
    width: auto;
    height: auto;
    overflow: visible;
    clip: auto;
    white-space: nowrap;
  }
  .select-marker :global(.select-icon) {
    display: block;
    width: var(--space-3);
    height: var(--space-3);
    flex-shrink: 0;
  }
  .opp-row:has(.cell-select input:focus-visible) .select-control {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .select-control:focus-within {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  /* title cell */
  .cell-title {
    display: flex;
    align-items: center;
    gap: 0;
    min-width: 0;
    background: transparent;
    border: none;
    padding: 0;
    text-align: left;
    cursor: pointer;
    color: inherit;
  }
  .cell-title:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 3px;
    border-radius: var(--radius-md);
  }
  /* The title IS the button that opens the detail view — give it a clear affordance. */
  .cell-title:hover .opp-title {
    color: var(--color-accent-dark);
    text-decoration: underline;
    text-underline-offset: 2px;
    text-decoration-thickness: 1px;
  }
  .title-block {
    display: flex;
    flex-direction: column;
    gap: 0.18rem;
    min-width: 0;
  }
  .opp-title-line {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.3rem 0.45rem;
  }
  .analyst-pick {
    color: var(--color-accent-dark);
    font-size: var(--text-xs);
    font-style: italic;
    font-weight: 600;
    line-height: 1.2;
    white-space: nowrap;
  }
  .opp-title {
    font-size: var(--text-base);
    font-weight: 700;
    letter-spacing: -0.005em;
    line-height: 1.2;
    color: var(--color-text-primary);
    transition: color var(--duration-fast) var(--ease-default);
    text-wrap: pretty;
  }
  .opp-summary {
    max-width: 72ch;
    font-size: var(--text-sm);
    line-height: 1.45;
    color: var(--color-text-secondary);
    display: -webkit-box;
    -webkit-line-clamp: 1;
    line-clamp: 1;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .opp-evidence {
    display: flex;
    gap: 0.32rem;
    align-items: baseline;
    max-width: 78ch;
    font-size: var(--text-11);
    line-height: 1.36;
    color: var(--color-text-secondary);
    min-width: 0;
    white-space: nowrap;
    overflow: hidden;
  }
  .opp-evidence strong {
    flex-shrink: 0;
    color: var(--color-text-secondary);
    font-weight: 700;
  }
  .opp-evidence span {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .opp-workshop-note {
    width: fit-content;
    max-width: 100%;
    overflow: hidden;
    color: var(--color-accent-dark);
    font-size: var(--text-11);
    font-weight: 700;
    line-height: 1.35;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .mobile-metrics {
    display: none;
  }
  .opp-tags {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.28rem;
    margin-top: 0.12rem;
  }
  .tag {
    display: inline-flex;
    align-items: center;
    max-width: 22rem;
    padding: 0.09rem 0.34rem;
    border-radius: var(--radius-md);
    font-family: var(--font-body);
    font-size: var(--text-xs);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    line-height: 1.18;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .tag-strength { border: 1px solid currentColor; }
  .tag-success {
    background: color-mix(in srgb, var(--color-success) 9%, transparent);
    color: var(--color-success-text);
  }
  .tag-angle {
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    color: var(--color-text-muted);
  }
  .tag-parity {
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    color: var(--color-text-muted);
    cursor: help;
  }
  .tag-risk {
    background: var(--color-error-subtle);
    border: 1px solid color-mix(in srgb, var(--color-error) 30%, transparent);
    color: var(--color-error-text);
  }
  .opp-merged-note {
    display: inline-flex;
    align-items: center;
    width: fit-content;
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--color-text-muted);
    cursor: help;
  }

  /* ── Variant grouping note ── */
  .variant-notes {
    display: grid;
    gap: 0.5rem;
    padding-top: 0.1rem;
  }
  .variant-note {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: 0.85rem;
    padding: 0.72rem 0.8rem;
    border-left: 2px solid var(--color-border);
    border-radius: var(--radius-md);
    background: color-mix(in srgb, var(--color-accent) 4%, var(--color-bg-surface));
  }
  .variant-note-copy {
    display: grid;
    gap: 0.22rem;
    min-width: 0;
  }
  .variant-note-copy > strong {
    color: var(--color-text-primary);
    font-size: var(--text-13);
    line-height: 1.25;
  }
  .variant-note-kicker {
    font-family: var(--font-mono);
    color: var(--color-text-secondary);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.055em;
    text-transform: uppercase;
  }
  .variant-note-names {
    display: flex;
    flex-wrap: wrap;
    gap: 0.22rem 0.5rem;
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: 1.35;
  }
  .variant-note-names span:not(:last-child)::after {
    content: "·";
    margin-left: 0.5rem;
    color: var(--color-border-emphasis);
  }
  .variant-note-action {
    min-height: 2.2rem;
    padding: 0.42rem 0.68rem;
    border: 1px solid var(--color-border-emphasis);
    border-radius: var(--radius-md);
    background: var(--color-bg-elevated);
    color: var(--color-text-primary);
    font-size: var(--text-sm);
    font-weight: 700;
    white-space: nowrap;
    cursor: pointer;
    transition: transform var(--duration-fast) var(--ease-default), border-color var(--duration-fast) var(--ease-default), color var(--duration-fast) var(--ease-default);
  }
  .variant-note-action:hover {
    border-color: var(--color-accent);
    color: var(--color-accent-dark);
  }
  .variant-note-action:active { transform: scale(0.98); }
  @media (prefers-reduced-motion: reduce) {
    .variant-note-action { transition: none; }
    .variant-note-action:active { transform: none; }
  }
  .variant-note-hint {
    color: var(--color-text-muted);
    font-size: var(--text-11);
    white-space: nowrap;
  }

  /* metric cells */
  .cell-metric,
  .cell-metric-head {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 0.34rem;
    font-variant-numeric: tabular-nums;
  }
  .cell-metric-head {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    /* -secondary, not -muted: 10-11px mono caps on the surface-tinted header
       row needs more than muted's 4.32:1. */
    color: var(--color-text-secondary);
    background: transparent;
    border: none;
    cursor: pointer;
    width: 100%;
    min-height: 2.5rem;
    padding: 0.25rem 0;
    border-radius: var(--radius-sm);
    transition: color var(--duration-fast) var(--ease-default);
  }
  .cell-metric-head:hover {    color: var(--color-text-primary);
  }
  .sort-arrow {
    display: inline-flex;
    flex-shrink: 0;
    align-items: center;
  }
  .sort-arrow.is-idle { visibility: hidden; }
  .cell-metric-head.active { color: var(--color-accent-dark); }
  @media (prefers-reduced-motion: reduce) {
    .cell-metric-head { transition: none; }
  }
  .metric-num {
    font-family: var(--font-mono);
    font-size: var(--text-13);
    font-weight: 800;
    color: var(--color-text-primary);
    line-height: 1;
  }
  .metric-unit {
    font-size: var(--text-xs);
    font-weight: 600;
    color: var(--color-text-muted);
    margin-left: 0.05rem;
  }
  .fit-success { color: var(--color-success-text); }
  .fit-warning { color: var(--color-text-primary); }
  .fit-muted { color: var(--color-text-muted); }
  .metric-score { align-items: flex-end; }
  .metric-score .metric-num { font-size: var(--text-base); }
  .metric-build-num {
    max-width: 5.8rem;
    font-size: var(--text-sm);
    font-weight: 700;
    color: var(--color-text-secondary);
    line-height: 1.08;
    text-align: right;
  }
  .copilot-shortlist-review {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1rem;
  }
  .copilot-shortlist-review section {
    min-width: 0;
    padding: 1rem;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-bg-subtle);
  }
  .copilot-shortlist-proposed {
    border-color: color-mix(in srgb, var(--color-accent) 45%, var(--color-border)) !important;
    background: color-mix(in srgb, var(--color-accent) 5%, var(--color-bg-subtle)) !important;
  }
  .copilot-shortlist-label {
    margin: 0 0 0.55rem;
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-11);
    font-weight: 800;
    letter-spacing: 0.07em;
    text-transform: uppercase;
  }
  .copilot-shortlist-review ol {
    display: grid;
    gap: 0.5rem;
    margin: 0;
    padding-left: 1.25rem;
  }
  .copilot-shortlist-review li {
    color: var(--color-text-primary);
    font-size: var(--text-base);
    font-weight: 600;
    line-height: 1.4;
  }
  .copilot-shortlist-empty,
  .copilot-shortlist-rationale p,
  .copilot-shortlist-error { margin: 0; }
  .copilot-shortlist-empty,
  .copilot-shortlist-rationale p {
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    line-height: 1.5;
  }
  .copilot-shortlist-rationale {
    grid-column: 1 / -1;
    padding-top: 0.25rem;
  }
  .copilot-shortlist-error {
    grid-column: 1 / -1;
    color: var(--color-error-text);
    font-size: var(--text-13);
  }
  .copilot-shortlist-cancel,
  .copilot-shortlist-apply {
    min-height: 2rem;
    padding: 0 0.75rem;
    border-radius: var(--radius-md);
    font-size: var(--text-13);
    font-weight: 600;
    cursor: pointer;
  }
  .copilot-shortlist-cancel {
    border: 1px solid var(--color-input-border);
    background: transparent;
    color: var(--color-text-secondary);
  }
  .copilot-shortlist-cancel:hover {
    border-color: var(--color-text-secondary);
    background: var(--color-bg-surface);
    color: var(--color-text-primary);
  }
  .copilot-shortlist-apply {
    border: 0;
    background: var(--color-accent-hover);
    color: var(--color-text-on-accent);
  }
  .copilot-shortlist-apply:hover:not(:disabled) {
    background: var(--color-accent-dark);
  }
  .copilot-shortlist-apply:disabled {
    background: var(--color-bg-hover);
    color: var(--color-text-muted);
    cursor: wait;
  }
  /* ── Responsive ── */
  @media (max-width: 859px) {
    .workbench { padding: var(--space-3) var(--space-3) var(--space-5); }
    .workbench-shell { padding-bottom: calc(var(--decision-rail-height, var(--space-20)) + var(--space-4)); }
    .decision-guide {
      grid-template-columns: 1fr;
      gap: var(--space-4);
    }
    .idea-expansion-row {
      align-items: flex-start;
      flex-direction: column;
    }
    .idea-expansion-row button {
      width: 100%;
      text-align: left;
    }
    /* No mobile override for .chat-launcher: it used to hardcode 144px, which discarded
       the measured --decision-rail-height the base rule consumes — and mobile is where the
       dock is MOST variable (below 40rem it goes full-bleed at bottom:0, wraps to two rows,
       and adds env(safe-area-inset-bottom)). The base rule already clears a bottom:0 dock
       correctly; re-adding a constant here just reintroduces the collision. */
    .copilot-shortlist-review { grid-template-columns: 1fr; }
    .cmd {
      grid-template-columns: 1fr;
      align-items: flex-start;
    }
    .cmd-title { max-width: none; }
    .cmd-status {
      width: 100%;
      padding: 0.65rem 0 0;
      border-left: 0;
      border-top: 1px solid var(--color-border);
    }
    .vote-tally {
      justify-content: flex-start;
    }
    .vote-tally-hint {
      justify-self: start;
      text-align: left;
    }
    .variant-note {
      grid-template-columns: minmax(0, 1fr);
      align-items: start;
    }
    .variant-note-action {
      width: 100%;
    }
    .opp-row {
      grid-template-columns: 2rem minmax(0, 1fr) 4.5rem;
      grid-template-areas:
        "rank title score"
        "pick pick pick";
      gap: 0.7rem 0.75rem;
      padding: 0.92rem;
      border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 54%, transparent);
      border-radius: var(--radius-lg, 0.875rem);
      background: var(--color-bg-elevated);
    }
    .opp-list {
      gap: 0.55rem;
      overflow: visible;
      background: transparent;
      border: 0;
      border-radius: var(--radius-none);
      box-shadow: none;
    }
    .opp-row-head { display: none; }
    .cell-metric.metric-fit,
    .cell-metric:not(.metric-score):not(.metric-fit),
    .cell-metric.metric-build {
      display: none;
    }
    .cell-rank {
      grid-area: rank;
      align-self: start;
      padding-top: 0.1rem;
      text-align: left;
    }
    .cell-select {
      grid-area: pick;
    }
    .cell-title {
      grid-area: title;
    }
    .metric-score {
      grid-area: score;
      align-self: start;
    }
    .metric-score { align-items: flex-end; }
    .opp-summary {
      -webkit-line-clamp: 2;
      line-clamp: 2;
    }
    .mobile-metrics {
      display: flex;
      flex-wrap: wrap;
      gap: 0.28rem 0.56rem;
      margin-top: 0.08rem;
      color: var(--color-text-muted);
      font-size: var(--text-11);
      line-height: 1.2;
    }
    .mobile-metrics strong {
      color: var(--color-text-secondary);
      font-family: var(--font-mono);
      font-weight: 800;
      font-variant-numeric: tabular-nums;
    }
    .tag { max-width: 13rem; }
    .select-control {
      width: 100%;
      min-height: 2.25rem;
      font-size: var(--text-sm);
    }
    /* visitor mode: anchor the vote pill as a full-width tap target (same
       affordance as the owner's full-width Shortlist control above) */
    .cell-action :global(> div) {
      width: 100%;
    }
    .cell-action :global(button) {
      width: 100%;
      justify-content: center;
      min-height: 2.25rem;
    }
  }

  @media (max-width: 480px) {
    .cmd-sub { font-size: var(--text-13); }
    .regen-focus {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      width: 100%;
    }
    .regen-focus-btn {
      min-height: 2.75rem;
      padding: 0.4rem 0.46rem;
      font-size: var(--text-11);
      line-height: 1.2;
      white-space: normal;
    }
  }

</style>
