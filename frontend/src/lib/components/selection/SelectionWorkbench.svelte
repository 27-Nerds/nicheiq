<script lang="ts">
  import { goto, replaceState } from "$app/navigation";
  import { page } from "$app/state";
  import type { Snippet } from "svelte";
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
    PRICE_CHANGED_RELOAD,
    PRICE_CHANGED_RETRY,
    VERDICT_EYEBROW,
    actionBody,
    appendixMetaLine,
    candidateStatsLine,
    generateNewBatchLabel,
    groupForMode,
    type CockpitMode,
  } from "$lib/selection/labels";
  import {
    selectSolution,
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
  import { chatLedger } from "$lib/stores/chatLedger.svelte";
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
  import type { SelectionExperimentDraftSeed, SelectionExperimentPrefill } from "$lib/types/selectionExperiment";
  import type {
    SelectionDecisionNextAction,
    SelectionDecisionState,
  } from "$lib/types/selectionDecisionState";
  import type { RuledOutFinding, OverlapGroup, MarketReality } from "$lib/types/report";
  import {
    computeCompositeScore,
    solutionDisplayTitle,
    solutionCardDescription,
    solutionStrengthBadge,
    fitLabel,
    opportunityShape,
  } from "$lib/utils/solution-utils";
  import { SCORE_DEFINITIONS } from "$lib/utils/scoreDefinitions";
  import { humanizeTag, tagDescription } from "$lib/utils/ideaTagLabels";
  import { angleLabel, angleDescription } from "$lib/utils/ideaAngleLabels";
  import {
    buildIdeaReferences,
    matchIdeaReferences,
    type IdeaReference,
  } from "$lib/utils/ideaReferences";
  import Tooltip from "$lib/components/ui/Tooltip.svelte";
  import WorkspaceOverlay from "$lib/components/ui/WorkspaceOverlay.svelte";
  import SelectSolutionModal from "$lib/components/SelectSolutionModal.svelte";
  import SolutionDetail from "$lib/components/SolutionDetail.svelte";
  import DecisionBrief from "$lib/components/selection/DecisionBrief.svelte";
  import ExperimentWorkspace from "$lib/components/selection/ExperimentWorkspace.svelte";
  import DecisionCockpit from "$lib/components/selection/DecisionCockpit.svelte";
  import ConceptForge from "$lib/components/selection/ConceptForge.svelte";
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
  import { buildSelectionJourney, type SelectionJourneyTask } from "$lib/selection/decisionJourney";

  const MAX_SELECTIONS = 3;

  interface Props {
    jobId: string;
    solutions: SolutionPreview[];
    creditBalance: number;
    stageCosts?: StageCosts;
    canRegenerate?: boolean;
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
    /** Emits the decision-journey tasks so the job-page sidebar (PhaseNav) can
     *  render the same two primary decision tools, with the same status, that
     *  the launchpad shows — one status source across the shell. */
    onJourneyTasks?: (tasks: SelectionJourneyTask[] | undefined) => void;
    /** Fired once a submitted idea seed settles (accepted/demoted/failed/refunded).
     *  SSE's sorted-name diff misses a same-name demotion/score change and can't see
     *  a brand-new ruled-out entry at all — the parent must force BOTH getSolutions()
     *  and getPreviewReport() here rather than rely on the existing SSE reconciliation. */
    onSeedSettled?: (outcome: "accepted" | "demoted" | "failed" | "refunded") => void;
    /** Visitor (read-only) mode: shortlist/Deep-Research affordances are replaced by
     *  the per-row actionSlot (vote button on the shared view). */
    interactive?: boolean;
    totalVotes?: number;
    actionSlot?: Snippet<[{ solution: SolutionPreview; index: number }]>;
  }

  let {
    jobId,
    solutions,
    creditBalance,
    stageCosts = { ...DEFAULT_STAGE_COSTS },
    canRegenerate = false,
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
    onComplete,
    onRegenerateStart,
    onJourneyTasks,
    onSeedSettled,
    interactive = true,
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
  const ideaReferences = $derived(
    buildIdeaReferences(solutions, examinedRuledOut ?? []),
  );
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
  let modalOpen = $state(false);
  let compareOpen = $state(false);
  let conceptForgeOpen = $state(false);
  let conceptForgeParentKeys = $state<string[] | null>(null);
  let copilotConceptForgePrefill = $state<SelectionConceptForgePrefill | null>(null);
  let experimentWorkspaceOpen = $state(false);
  let compareStartMode = $state<"risk" | "assumptions" | "market" | "fit" | "challenge">("market");
  let variantReview = $state<{
    patch: IdeaSynthesisPatch;
    parentRefs: { ideaId: string; ideaRevision: number }[];
    sourceMessageId: string;
    childIdeaId: string;
    childIdeaRevision: number;
  } | null>(null);
  let overlapComparison = $state<{ ideaKeys: string[]; sharedProduct: string } | null>(null);
  let copilotComparisonKeys = $state<string[] | null>(null);
  let directWorkspaceFocus = $state(false);
  let copilotChallengeFocus = $state<{
    requestId: number;
    ideaId: string;
    ideaRevision: number;
    lens: SelectionChallengeLens;
    challengeId?: string;
    questionId?: string;
  } | null>(null);
  let copilotFocusSequence = 0;
  let copilotShortlistReview = $state<{
    requestId: string;
    expectedVersion: number;
    ideas: SolutionPreview[];
    rationale: string;
  } | null>(null);
  let copilotShortlistError = $state("");
  let copilotAssumptionPrefill = $state<SelectionAssumptionPrefill | null>(null);
  let copilotOwnerEvidencePrefill = $state<SelectionOwnerEvidencePrefill | null>(null);
  let experimentPrefill = $state<SelectionExperimentPrefill | null>(null);
  let activeDecisionProfile = $state<SelectionDecisionProfile | null>(null);
  let decisionProfileSyncJobId = $state("");
  let pendingDecisionProfileKey = $state<string | null>(null);
  let staleDecisionProfileKey = $state<string | null>(null);
  let selectLoading = $state(false);
  let selectError = $state("");
  let modalIndex = $state<number | null>(null); // index into original `solutions`
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
  let handledSelectionToolQuery = $state("");

  function ideaKey(solution: SolutionPreview): string {
    return solution.idea_id ?? solution.solution_name;
  }

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
          shortlistSaveError = "This shortlist contains a candidate without a stable identity. Refresh and try again.";
          break;
        }
        try {
          const saved = await saveSelectionDraft(jobId, shortlistDraftVersion, items);
          shortlistDraftVersion = saved.version;
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
          item => ideaKey(item) === storedKey || item.solution_name === storedKey,
        );
        if (solution) selectedIdeaKeys.add(ideaKey(solution));
      }
    }
    shortlistDraftVersion = selectionDraft?.version ?? 0;
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
  let experimentWorkspaceRef: ExperimentWorkspace | undefined = $state();
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

  function askAnalystAboutCockpit(
    mode: "risk" | "assumptions" | "market" | "fit" | "challenge",
    ideas: SolutionPreview[],
  ) {
    const viewLabel = {
      risk: "decision risks",
      assumptions: "tracked assumptions",
      market: "market comparison",
      fit: "founder fit",
      challenge: "evidence checks",
    }[mode];
    const ideaContext = ideas
      .map((idea) => '"' + solutionDisplayTitle(idea) + '" (revision ' + (idea.idea_revision ?? 1) + ')')
      .join(" and ");
    analystStarterPrompt =
      `Help me review ${viewLabel} for ${ideaContext}. Walk me through the evidence and trade-offs in this view. `
      + "Answer in plain prose; only prepare a draft form if I explicitly ask you to.";
    // The cockpit stays open — the analyst dock coexists with it (see the
    // analyst-dock z-index override below, which lifts the dock above the
    // cockpit's modal layer so both stay usable).
    chatPanel.open();
  }



  // ── Regeneration state ──
  let regenerating = $state(false);
  let regenerateError = $state("");
  let regenerateOverlayOpen = $state(false);
  const canAffordRegenerate = $derived(
    creditBalance >= stageCosts.regenerate_ideas,
  );
  const REGEN_FOCUSES = [
    { value: "auto", label: "Auto" },
    { value: "novelty", label: "Novelty" },
    { value: "distribution", label: "Distribution" },
  ] as const;
  let regenerateFocus = $state<"auto" | "novelty" | "distribution">("auto");
  $effect(() => {
    if (!isRegenerating && regenerating) regenerating = false;
  });

  // `focusOverride` lets the chat patch card ("Apply changes") drive the same
  // call the manual focus buttons use, instead of duplicating the credit/402
  // handling in ChatThread — the tool only ever proposes a change; this is the
  // one place it's actually applied (regenerate-ideas route, unchanged).
  async function handleRegenerate(focusOverride?: IdeaFocus) {
    if (regenerating || isRegenerating || seedPending || chatLedger.hasPendingSeed) return;
    const focus = focusOverride ?? regenerateFocus;
    regenerateFocus = focus;
    regenerating = true;
    regenerateError = "";
    chatThreadRef?.stopStreaming();
    try {
      await regenerateIdeas(
        jobId,
        focus === "auto" ? undefined : focus,
      );
      regenerateOverlayOpen = false;
      onRegenerateStart?.();
    } catch (e) {
      if (e instanceof ApiError && e.status === 402) {
        creditTopUp.show({
          balance: creditBalance,
          required: stageCosts.regenerate_ideas,
          stageName: "idea regeneration",
        });
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
  let seedHighlightName = $state<string | null>(null);
  let seedHighlightRuledOutIndex = $state<number | null>(null);
  let seedBanner = $state<{ outcome: "accepted" | "demoted" | "failed" | "refunded" } | null>(null);

  // One paid pool-mutation operation at a time (mirrors the backend's single
  // `Job.activeDispatchId`) — gates the seed card, regenerate, shortlist toggles,
  // detail-select, confirm-selection, and chat compose. Backend CAS stays the
  // authoritative guard; this is UX-only. `chatLedger.hasPendingSeed` folds in the
  // durable (reload-surviving) case, not just this session's own submit.
  const poolMutationBusy = $derived(
    regenerating || isRegenerating || seedPending || chatLedger.hasPendingSeed,
  );

  function stopSeedPoll() {
    if (seedPollTimer) {
      clearInterval(seedPollTimer);
      seedPollTimer = null;
    }
  }

  function scrollBehavior(): ScrollBehavior {
    return matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
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
    stopSeedPoll();
    inFlightSeed = { sourceMessageId, priorNames, priorRuledOutCount };
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
        stopSeedPoll();
        inFlightSeed = null;
        seedPending = false;
      }
    }, 6000);
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
      return { ok: false, message: "Another candidate update is still running." };
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
          : `Replaced ${selectedParents.length} source candidates with the combined variant.`,
      };
    }
    if (selectedIdeaKeys.size >= MAX_SELECTIONS) {
      return { ok: false, message: "Shortlist is full. Remove one candidate first." };
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
    overlapComparison = null;
    copilotComparisonKeys = null;
    variantReview = {
      patch,
      parentRefs: resolved.parents.map((parent) => ({
        ideaId: parent.idea_id!,
        ideaRevision: parent.idea_revision ?? 1,
      })),
      sourceMessageId,
      childIdeaId: resolved.child.idea_id!,
      childIdeaRevision: resolved.child.idea_revision ?? 1,
    };
    compareStartMode = "market";
    compareOpen = true;
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
  const bestScore = $derived.by(() =>
    solutions.length
      ? Math.round(Math.max(...solutions.map((s) => computeCompositeScore(s))) * 100)
      : null,
  );
  const cmdStatsLine = $derived(
    candidateStatsLine({ candidates: solutions.length, topScore: bestScore, segments: segmentCount }),
  );

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
    });
  });
  $effect(() => {
    onJourneyTasks?.(selectionJourney?.tasks);
  });
  const railResearchLead = $derived.by(() => {
    if (selectionJourney?.recommendation.target !== "shortlist") return null;
    const recommendedIdea = selectionJourney.recommendation.ideas[0];
    if (!recommendedIdea) return null;
    return solutions.find((idea) =>
      idea.idea_id === recommendedIdea.ideaId
      && (idea.idea_revision ?? 1) === recommendedIdea.ideaRevision
    ) ?? null;
  });
  const conceptForgeParents = $derived.by(() => conceptForgeParentKeys
    ? conceptForgeParentKeys.map(solutionForKey).filter((idea): idea is SolutionPreview => Boolean(idea))
    : selectedIdeas);
  const selectedIdeaKeyList = $derived(Array.from(selectedIdeaKeys));

  const resolvedVariantReview = $derived.by(() => {
    const review = variantReview;
    if (!review) return null;
    const parents = review.parentRefs.map((parentRef) => solutions.find((idea) =>
      idea.idea_id === parentRef.ideaId
      && (idea.idea_revision ?? 1) === parentRef.ideaRevision
    ));
    if (parents.some((parent) => !parent)) return null;
    const expectedKeys = review.parentRefs.map(
      (parentRef) => `${parentRef.ideaId}:${parentRef.ideaRevision}`,
    );
    const child = solutions.find((idea) =>
      idea.idea_id === review.childIdeaId
      && (idea.idea_revision ?? 1) === review.childIdeaRevision
      && idea.synthesis_operation === review.patch.operation
      && idea.synthesis_source_message_id === review.sourceMessageId
      && idea.synthesized_from?.length === expectedKeys.length
      && expectedKeys.every((key) => idea.synthesized_from?.some(
        (source) => `${source.idea_id}:${source.idea_revision}` === key,
      ))
    );
    return child ? { parents: parents as SolutionPreview[], child } : null;
  });
  const resolvedOverlapComparison = $derived.by(() => {
    if (!overlapComparison) return null;
    const ideas = overlapComparison.ideaKeys
      .map(solutionForKey)
      .filter((idea): idea is SolutionPreview => Boolean(idea));
    return ideas.length === overlapComparison.ideaKeys.length
      ? { ...overlapComparison, ideas }
      : null;
  });
  const resolvedCopilotComparison = $derived.by(() => {
    if (!copilotComparisonKeys) return null;
    const ideas = copilotComparisonKeys
      .map(solutionForKey)
      .filter((idea): idea is SolutionPreview => Boolean(idea));
    return ideas.length === copilotComparisonKeys.length ? ideas : null;
  });
  const comparisonIdeas = $derived(
    resolvedVariantReview
      ? [...resolvedVariantReview.parents, resolvedVariantReview.child]
      : resolvedCopilotComparison ?? resolvedOverlapComparison?.ideas ?? selectedIdeas,
  );
  const comparisonContext = $derived(
    directWorkspaceFocus && resolvedCopilotComparison
      ? {
          dialogLabel: "Candidate evidence review",
          title: "Review candidate evidence",
          intro: "Review this exact candidate revision. Nothing changes until you choose an owner action.",
          regionLabel: "Focused candidate evidence review",
        }
      : resolvedCopilotComparison
      ? {
          dialogLabel: "Review analyst-selected candidates",
          title: resolvedCopilotComparison.length > 1 ? "Compare suggested candidates" : "Review suggested candidate",
          intro: "The analyst prepared this view from current candidate revisions. Nothing changes until you use an existing owner action.",
          regionLabel: "Analyst-selected candidate review",
        }
      : resolvedOverlapComparison
      ? {
          dialogLabel: "Compare similar candidates",
          title: resolvedOverlapComparison.sharedProduct
            ? `Resolve ${resolvedOverlapComparison.sharedProduct} variants`
            : "Resolve similar candidates",
          intro: "Research grouped these as one buyer-visible product. They remain separate candidates, so compare their trade-offs before shortlisting one.",
          regionLabel: "Similar candidate comparison",
        }
      : null,
  );
  const variantComparisonContext = $derived.by(() => {
    const review = variantReview;
    if (!review || !resolvedVariantReview) return null;
    return {
      operation: review.patch.operation,
      changeSummary: review.patch.changeSummary,
      sourceContributions: review.parentRefs.map((parentRef) =>
        review.patch.parents.find((candidate) =>
          candidate.ideaId === parentRef.ideaId
          && candidate.ideaRevision === parentRef.ideaRevision
        )?.contribution ?? "Original research basis retained."
      ),
      requiresValidation: review.patch.evidence.requiresValidation,
      conclusionOutcome:
        review.patch.evidence.experimentConclusionRefs?.[0]?.outcome ?? null,
    };
  });

  function useReviewedVariant(): { ok: boolean; message?: string } {
    return resolvedVariantReview
      ? addVariantToShortlist(resolvedVariantReview.parents, resolvedVariantReview.child)
      : { ok: false, message: "The compared revisions are no longer available." };
  }

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
    variantReview = null;
    copilotComparisonKeys = null;
    directWorkspaceFocus = false;
    overlapComparison = {
      ideaKeys: group.comparisonIdeas.map(ideaKey),
      sharedProduct: group.sharedProduct,
    };
    compareStartMode = "market";
    compareOpen = true;
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
    if (k === "score") return computeCompositeScore(s);
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

  // Suggested questions name the ACTUAL ranked candidates and the actions open right
  // now (shortlist, regenerate, or step back and question the niche) — recomputed as
  // the ranking, the shortlist, and the conversation change.
  const chatSuggestions = $derived(
    selectionSuggestions({
      solutions: sortedSolutions,
      messages: chatLedger.segmentMessages(5),
      weakPool,
      canRegenerate: canRegenerate && !regenerating && !isRegenerating,
      hasSelection: selectionCount > 0,
      collaboratorRationaleCount,
      poolMutationBusy,
    }),
  );

  const SORT_COLS: { key: SortKey; label: string; tooltip?: string }[] = [
    { key: "score", label: "Score", tooltip: SCORE_DEFINITIONS.composite },
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
  function rankedIndexOf(identifier: string): number {
    return sortedSolutions.findIndex((solution) => ideaKey(solution) === identifier || solution.solution_name === identifier);
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
  function toggleComparedIdea(idea: SolutionPreview): void {
    if (!resolvedOverlapComparison) return;
    toggle(ideaKey(idea));
  }
  // SolutionDetail still emits its display name; resolve it back to the current exact idea.
  function handleToggleAdapter(name: string) {
    const current = modalIndex === null ? undefined : sortedSolutions[modalIndex];
    const solution = current?.solution_name === name ? current : solutions.find((item) => item.solution_name === name);
    if (solution) toggle(ideaKey(solution));
  }
  // Overlay exclusivity: exactly one of these surfaces is open at a time.
  // Every opener below resets through here BEFORE assigning its own payload,
  // so a payload set before this call would be wiped out — never touch state
  // owned by this list until after calling it. chatPanel is never touched
  // here; its dock/expand/close state is independent of overlay exclusivity.
  function closeAllOverlays(): void {
    modalIndex = null;
    ruledOutDetail = null;
    modalOpen = false;
    compareOpen = false;
    conceptForgeOpen = false;
    experimentWorkspaceOpen = false;
    regenerateOverlayOpen = false;
    overlapComparison = null;
    variantReview = null;
    copilotComparisonKeys = null;
    copilotChallengeFocus = null;
    copilotAssumptionPrefill = null;
    copilotOwnerEvidencePrefill = null;
    copilotConceptForgePrefill = null;
    conceptForgeParentKeys = null;
    experimentPrefill = null;
    copilotShortlistReview = null;
    copilotShortlistError = "";
    decisionBriefRef?.closeEditor?.();
  }

  function openDetail(identifier: string) {
    closeAllOverlays();
    modalIndex = rankedIndexOf(identifier);
  }
  function handleNavigate(index: number) {
    modalIndex = index;
  }
  function handleCloseDetail() {
    modalIndex = null;
    restoreChatAfterDetail();
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
      openDetail(reference.solutionName);
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
    if (!canAffordDeep) {
      creditTopUp.show({
        balance: creditBalance,
        required: deepCost,
        stageName: "deep research",
      });
      return;
    }
    selectError = "";
    closeAllOverlays();
    modalOpen = true;
  }

  function handleExperimentPrefill(draft: SelectionExperimentDraftSeed) {
    closeAllOverlays();
    experimentPrefill = { requestId: crypto.randomUUID(), draft };
    experimentWorkspaceOpen = true;
  }

  function openDecisionMode(mode: CockpitMode) {
    if (selectionCount === 0 || poolMutationBusy) return;
    closeAllOverlays();
    compareStartMode = mode;
    compareOpen = true;
  }

  function openFounderContext() {
    closeAllOverlays();
    decisionBriefRef?.openEditor();
  }

  function openExperimentWorkspace() {
    closeAllOverlays();
    experimentWorkspaceOpen = true;
  }

  async function openFocusedExperimentFromQuery(): Promise<void> {
    const ideaId = page.url.searchParams.get("ideaId");
    const ideaRevision = Number(page.url.searchParams.get("ideaRevision") ?? "1");
    if (!ideaId || !Number.isInteger(ideaRevision) || ideaRevision < 1) {
      openExperimentWorkspace();
      return;
    }
    const idea = solutions.find((solution) => (
      solution.idea_id === ideaId && (solution.idea_revision ?? 1) === ideaRevision
    ));
    if (!idea) {
      selectError = "That candidate revision is no longer available. Return to the test workspace and choose a current candidate.";
      return;
    }

    const assumptionId = page.url.searchParams.get("assumptionId");
    if (!assumptionId) {
      handleExperimentPrefill({ ideaId, ideaRevision });
      return;
    }

    try {
      const state = selectionDecisionState ?? await getSelectionDecisionState(jobId);
      const assumption = state.assumptions.find((item) => (
        item.id === assumptionId
        && item.idea.ideaId === ideaId
        && item.idea.ideaRevision === ideaRevision
      ));
      if (!assumption) {
        selectError = "That assumption is stale or belongs to another candidate. Return to the test workspace and choose a current assumption.";
        return;
      }
      handleExperimentPrefill({
        ideaId,
        ideaRevision,
        assumptionId: assumption.id,
        assumption: assumption.statement,
        whyCritical: assumption.impact,
        originChallengeId: assumption.originChallengeId,
        originQuestionId: assumption.originQuestionId,
      });
    } catch (error) {
      selectError = error instanceof Error
        ? error.message
        : "We couldn't open that test plan. Try again.";
    }
  }

  function openFocusedRiskFromQuery(): void {
    const ideaId = page.url.searchParams.get("ideaId");
    const ideaRevision = Number(page.url.searchParams.get("ideaRevision") ?? "1");
    const requestedLens = page.url.searchParams.get("lens");
    const lens = requestedLens === "demand"
      || requestedLens === "distribution"
      || requestedLens === "competition"
      || requestedLens === "dependencies"
      ? requestedLens
      : "demand";
    const idea = solutions.find((solution) => (
      solution.idea_id === ideaId && (solution.idea_revision ?? 1) === ideaRevision
    ));
    if (!idea?.idea_id) {
      selectError = "That candidate revision is no longer available. Return to the evidence workspace and choose a current candidate.";
      return;
    }
    closeAllOverlays();
    directWorkspaceFocus = true;
    copilotComparisonKeys = [ideaKey(idea)];
    copilotChallengeFocus = {
      requestId: ++copilotFocusSequence,
      ideaId: idea.idea_id,
      ideaRevision,
      lens,
    };
    compareStartMode = "challenge";
    compareOpen = true;
  }


  function selectionWorkspaceHref(
    workspace: "compare" | "risks" | "tests" | "alternatives",
    options?: {
      view?: "market" | "founder";
      /** Opens a tool on arrival. The workspace strips these once handled, so
       *  they never linger as stale overlay state in the URL. */
      tool?: "compare" | "fit" | "challenge" | "assumptions" | "tests" | "variants";
      lens?: SelectionChallengeLens | null;
      focus?: { ideaId: string; ideaRevision: number } | null;
    },
  ): string {
    const params = new URLSearchParams();
    for (const idea of selectedIdeas.slice(0, MAX_SELECTIONS)) {
      if (idea.idea_id) params.append("idea", `${idea.idea_id}:${idea.idea_revision ?? 1}`);
    }
    if (options?.view) params.set("view", options.view);
    if (options?.tool) params.set("tool", options.tool);
    if (options?.lens) params.set("lens", options.lens);
    if (options?.focus) {
      params.set("ideaId", options.focus.ideaId);
      params.set("ideaRevision", String(options.focus.ideaRevision));
    }
    const query = params.toString();
    return `/jobs/${encodeURIComponent(jobId)}/selection/${workspace}${query ? `?${query}` : ""}`;
  }

  function openCandidatePool() {
    const candidatePool = document.querySelector('[data-annotation-anchor="shortlist-candidates"]');
    if (!(candidatePool instanceof HTMLElement) || typeof candidatePool.scrollIntoView !== "function") return;
    candidatePool.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }

  /**
   * `?selectionTool=` used to be how the workspace pages reached their tools:
   * they navigated BACK here, which re-opened the tool over the job page rather
   * than the page the user launched it from. The workspace now hosts its own
   * tools and nothing links here that way any more; the handler stays only so
   * existing bookmarks keep working.
   *
   * The params are stripped once handled. They are a one-shot instruction, not
   * overlay state: leaving them in the URL meant closing an overlay left a
   * stale `selectionTool` behind, so a refresh re-opened a tool the user had
   * already dismissed, and a later overlay ran under a URL naming a different
   * one.
   */
  $effect(() => {
    if (!interactive) return;
    const tool = page.url.searchParams.get("selectionTool");
    if (!tool) return;
    const key = `${jobId}:${tool}:${page.url.search}`;
    if (handledSelectionToolQuery === key) return;
    handledSelectionToolQuery = key;

    const openTool = () => {
      if (tool === "constraints") return openFounderContext();
      if (tool === "analyst") return chatPanel.open();
      if (tool === "tests") {
        void openFocusedExperimentFromQuery();
        return;
      }
      if (tool === "alternatives") {
        closeAllOverlays();
        conceptForgeOpen = true;
        return;
      }
      if (selectionCount === 0) return;
      if (tool === "fit") return openDecisionMode("fit");
      if (tool === "assumptions") return openDecisionMode("assumptions");
      if (tool === "risks" && page.url.searchParams.has("ideaId")) return openFocusedRiskFromQuery();
      if (tool === "risks") return openDecisionMode("challenge");
      if (tool === "compare") return openDecisionMode("market");
    };

    queueMicrotask(() => {
      openTool();
      clearSelectionToolQuery();
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

  /** Empty test workspace → evidence challenge. openDecisionMode already
   *  resets through closeAllOverlays, so the cockpit is the only open
   *  surface once it lands. */
  function openChallengeFromTests() {
    if (selectionCount === 0 || poolMutationBusy) return;
    openDecisionMode("challenge");
  }

  /** Challenge finding → concept forge. The cockpit closes (with its usual
   *  cleanup) before the forge opens so only one overlay is up at a time.
   *  Reuses the same forge open path as the Shape tile (no preselected
   *  parents, no copilot brief). */
  function openForgeFromChallenge() {
    if (poolMutationBusy) return;
    closeAllOverlays();
    void loadSelectionDecisionState();
    conceptForgeOpen = true;
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
      selectionDecisionStateError = "The candidate changed while this suggestion was open. Refreshing it now.";
      void loadSelectionDecisionState();
      return;
    }

    if (action.kind === "select_candidate") {
      const idea = ideas[0];
      if (idea) openDetail(ideaKey(idea));
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
      if (ideas.length) void goto(selectionWorkspaceHref("compare", { view: "founder", tool: "fit" }));
      return;
    }
    if (action.kind === "stress_test_evidence") {
      const idea = ideas[0];
      if (!idea?.idea_id || !action.lens) return;
      void goto(selectionWorkspaceHref("risks", {
        tool: "challenge",
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
      void goto(selectionWorkspaceHref("tests", {
        tool: "tests",
        focus: idea?.idea_id ? { ideaId: idea.idea_id, ideaRevision: idea.idea_revision ?? 1 } : null,
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

  function showCopilotWorkspace(ideas: SolutionPreview[], mode: typeof compareStartMode): void {
    closeAllOverlays();
    copilotComparisonKeys = ideas.map(ideaKey);
    compareStartMode = mode;
    compareOpen = true;
    chatPanel.close();
  }

  function handleCopilotAction(
    action: SelectionCopilotAction,
    sourceMessageId: string,
  ): { ok: boolean; message?: string } {
    const resolvedIdeas = resolveCopilotIdeas(action);
    if (action.ideas.length > 0 && !resolvedIdeas) {
      return {
        ok: false,
        message: "This suggestion references an older candidate revision. Refresh the research and ask the analyst again.",
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
        return { ok: false, message: "The suggested shortlist must contain between one and three current candidates." };
      }
      copilotShortlistError = "";
      copilotShortlistReview = {
        requestId: sourceMessageId,
        expectedVersion: action.expectedVersion,
        ideas,
        rationale: action.rationale,
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
          return { ok: false, message: "This directions brief no longer matches one or two current candidates. Ask the analyst to prepare it again." };
        }
        closeAllOverlays();
        conceptForgeParentKeys = ideas.map(ideaKey);
        copilotConceptForgePrefill = {
          requestId: sourceMessageId,
          purpose: purpose as SelectionConceptForgePrefill["purpose"],
          targetTradeoff: typeof targetTradeoff === "string" ? targetTradeoff : "",
          rationale: action.rationale,
          caveats: action.caveats,
        };
        conceptForgeOpen = true;
        chatPanel.close();
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
          return { ok: false, message: "An experiment draft must reference exactly one current candidate." };
        }
        closeAllOverlays();
        experimentWorkspaceOpen = true;
        const result = experimentWorkspaceRef?.reviewCopilotDraft(
          sourceMessageId,
          {
            ...(action.values ?? {}),
            ideaId: idea.idea_id,
            ideaRevision: idea.idea_revision ?? 1,
          } as SelectionExperimentDraftSeed,
          action.record,
        );
        if (result?.ok) chatPanel.close();
        return result ?? { ok: false, message: "The experiment editor is not ready yet. Try again." };
      }
      if (action.target === "assumption" || action.target === "owner_evidence") {
        const idea = ideas[0];
        if (!idea?.idea_id || ideas.length !== 1 || !action.lens) {
          return { ok: false, message: "This draft must reference one current candidate and one evidence lens." };
        }
        const values = action.values ?? {};
        if (
          values.ideaId !== idea.idea_id
          || values.ideaRevision !== (idea.idea_revision ?? 1)
          || values.lens !== action.lens
        ) {
          return {
            ok: false,
            message: "The draft identity does not match its current candidate revision and evidence lens.",
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
          // showCopilotWorkspace resets these prefills via closeAllOverlays, so
          // the payload must be assigned AFTER it, not before.
          showCopilotWorkspace([idea], "assumptions");
          copilotAssumptionPrefill = assumptionPrefill;
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
        const evidenceChallengeFocus = {
          requestId: ++copilotFocusSequence,
          ideaId: idea.idea_id,
          ideaRevision: idea.idea_revision ?? 1,
          lens: action.lens,
          challengeId: action.origin?.challengeId,
          questionId: action.origin?.questionId,
        };
        // showCopilotWorkspace resets these prefills via closeAllOverlays, so
        // the payload must be assigned AFTER it, not before.
        showCopilotWorkspace([idea], "challenge");
        copilotOwnerEvidencePrefill = ownerEvidencePrefill;
        copilotChallengeFocus = evidenceChallengeFocus;
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
        return { ok: false, message: "A candidate action must reference exactly one current candidate." };
      }
      returnToChatState = chatPanel.isExpanded ? "expanded" : "docked";
      chatPanel.close();
      openDetail(ideaKey(idea));
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
        experimentWorkspaceOpen = true;
        const result = experimentWorkspaceRef?.reviewCopilotDraft(
          sourceMessageId,
          { ideaId: ideas[0].idea_id, ideaRevision: ideas[0].idea_revision ?? 1 },
          action.record,
        );
        if (result?.ok) chatPanel.close();
        return result ?? { ok: false, message: "The experiment workspace is not ready yet. Try again." };
      }
      chatPanel.close();
      openExperimentWorkspace();
      return { ok: true };
    }

    if (ideas.length === 0) {
      return { ok: false, message: "This action needs at least one current candidate reference." };
    }

    const mode = action.target === "risk_queue"
      ? "risk"
      : action.target === "assumptions" || action.target === "assumption"
        ? "assumptions"
        : action.target === "founder_fit"
          ? "fit"
          : action.target === "challenge" || action.target === "owner_evidence"
            ? "challenge"
            : "market";

    if (mode === "challenge" && (!action.lens || ideas.length !== 1 || !ideas[0].idea_id)) {
      return { ok: false, message: "An evidence action must include one current candidate and an evidence lens." };
    }
    const challengeFocus = mode === "challenge" && action.lens
      ? {
          requestId: ++copilotFocusSequence,
          ideaId: ideas[0].idea_id as string,
          ideaRevision: ideas[0].idea_revision ?? 1,
          lens: action.lens,
          challengeId: action.origin?.challengeId,
          questionId: action.origin?.questionId,
        }
      : null;
    // showCopilotWorkspace resets copilotChallengeFocus via closeAllOverlays,
    // so the focus payload must be assigned AFTER it, not before.
    showCopilotWorkspace(ideas, mode);
    if (challengeFocus) copilotChallengeFocus = challengeFocus;
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

  async function handleConfirmSelection(rationale: string) {
    if (poolMutationBusy) return;
    selectLoading = true;
    selectError = "";
    chatThreadRef?.stopStreaming();
    try {
      const solutionNames = selectedIdeas.map((solution) => solution.solution_name);
      const solutionIds = selectedIdeas.map((solution) => solution.idea_id).filter((id): id is string => Boolean(id));
      await selectSolution(jobId, {
        solutionNames,
        solutionIds,
        rationale: rationale || undefined,
      });
      modalOpen = false;
      onComplete?.();
    } catch (e) {
      if (e instanceof ApiError && e.status === 402) {
        modalOpen = false;
        creditTopUp.show({
          balance: creditBalance,
          required: deepCost,
          stageName: "deep research",
        });
      } else {
        selectError =
          e instanceof Error ? e.message : "Failed to select solution";
      }
    } finally {
      selectLoading = false;
    }
  }
  function handleCancelModal() {
    if (!selectLoading) {
      modalOpen = false;
      selectError = "";
    }
  }

  function scoreColor(v: number): string {
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
    const risk =
      s.tags?.risk_flags?.[0]
        ? humanizeTag(s.tags.risk_flags[0])
        : s.tags?.build_complexity === "high"
          ? "Hard to build"
          : s.tags?.novelty_level === "conventional"
            ? "Conventional"
            : null;
    const mergedFrom = s.idea_tier === "merged" ? (s.merged_from ?? []) : [];
    const parity = s.incumbent_parity?.trim();
    const incumbent =
      parity && !parity.toLowerCase().startsWith("none")
        ? { name: incumbentName(parity), full: parity }
        : null;
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
      score: computeCompositeScore(s),
      fit: fitLabel(s.market_fit_score),
      feasPct: pct(s.technical_feasibility_score),
      build: s.estimated_development_time ?? "--",
      strength: solutionStrengthBadge(s),
      angle: s.winning_angle && angleLabel(s.winning_angle),
      strengthWhy: s.tags?.primary_strength
        ? tagDescription(s.tags.primary_strength)
        : null,
      angleWhy:
        s.angle_rationale ||
        (s.winning_angle ? angleDescription(s.winning_angle) : null),
      provenance: sourcePain,
      risk,
      mergedCount: mergedFrom.length,
      mergedNames: mergedFrom.join(", "),
      synthesisLabel,
      synthesisParents: synthesisParents.map((parent) => parent.solution_name).join(", "),
      incumbent,
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
        <h2 class="cmd-title">Ranked candidates</h2>
        <p class="record-line cmd-stats" aria-label="Candidate summary">{cmdStatsLine}</p>
      </div>
      {#if interactive}
        <p class="cmd-sub">
          Compare, reshape, or shortlist up to 3 candidates. Deep Research checks demand,
          competition, market size, and go-to-market risk after you choose.
        </p>
      {:else}
        <p class="cmd-sub">
          Solution candidates from the discovery run, ranked by composite score.
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
      {#if regenerateError}
        <p class="regen-error" role="alert">{regenerateError}</p>
      {/if}

      {#if seedError}
        <p class="regen-error" role="alert">{seedError}</p>
      {/if}

      {#if seedBanner}
        <p class="seed-banner" role="status" class:seed-banner--accepted={seedBanner.outcome === "accepted"}>
          {#if seedBanner.outcome === "accepted"}
            Evaluation complete. The result was added to ranked candidates below.
          {:else if seedBanner.outcome === "demoted"}
            We tested your idea. It didn't clear the market-fit bar. See why below.
          {:else}
            Evaluation failed. Your credits were refunded.
          {/if}
        </p>
      {/if}

      <!-- ── Ranked opportunity list ── -->
      <div
        class="opp-list"
        role="table"
        aria-label="Ranked candidates"
        data-annotation-anchor="shortlist-candidates"
      >
    <!-- Column header (desktop) -->
    <div class="row row-head" role="row">
      <span class="cell-rank" role="columnheader">#</span>
      <span class="cell-select-label" role="columnheader">{interactive ? "Pick" : "Vote"}</span>
      <span class="cell-title-label" role="columnheader">Opportunity</span>
      {#each SORT_COLS as col}
        <!-- Explicit name: the subtree holds the sort-button label plus an
             sr-only definition, neither of which should become the column name
             every cell in this column is announced with. -->
        <span
          class="cell-shell"
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
            aria-describedby={col.tooltip ? `sort-tip-${col.key}` : undefined}
          >
            <span>{col.label}</span>
            {#if sortKey === col.key}
              {#if sortDir === "asc"}<ArrowUp class="w-3 h-3" aria-hidden="true" />{:else}<ArrowDown class="w-3 h-3" aria-hidden="true" />{/if}
            {/if}
            {#if col.tooltip}
              <span id="sort-tip-{col.key}" class="sr-only">{col.tooltip}</span>
            {/if}
          </button>
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
        class="row"
        role="row"
        class:row-sel={isSel}
        class:row-maxed={maxed}
        class:row-seed-highlight={seedHighlightName === s.solution_name}
        data-solution-name={s.solution_name}
        data-annotation-anchor={`candidate:${s.solution_name}`}
      >
        <span class="cell-rank" role="cell">{i + 1}</span>

        {#if interactive}
          <span class="cell-shell" role="cell">
          <label
            class="cell-select select-control"
            class:sel={isSel}
            class:maxed
            aria-disabled={maxed ? "true" : undefined}
          >
            <input
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
              <span class="select-marker"><Check class="select-check" aria-hidden="true" /></span>
              <span class="select-copy">Shortlisted</span>
            {:else if maxed}
              <span class="select-marker"><span class="select-dash" aria-hidden="true">-</span></span>
              <span class="select-copy">Full</span>
              <span id="select-maxed-hint-{i}" class="sr-only">Deselect one to add this</span>
            {:else}
              <span class="select-marker"><Plus class="select-plus w-3.5 h-3.5" aria-hidden="true" /></span>
              <span class="select-copy">Shortlist</span>
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
          onclick={() => openDetail(key)}
          aria-label={`Review details for ${m.title}`}
        >
          <span
            class="title-block"
            data-annotation-anchor={`candidate:${s.solution_name}:content`}
          >
            <span
              class="opp-title-line"
              data-annotation-anchor={`candidate:${s.solution_name}:title`}
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
              <Tooltip content={`Synthesized from: ${m.mergedNames}`} position="bottom">
                {#snippet children()}
                  <span class="opp-merged-note">Synthesized from {m.mergedCount} variant{m.mergedCount === 1 ? "" : "s"}</span>
                {/snippet}
              </Tooltip>
            {/if}
            {#if m.synthesisLabel}
              <span class="opp-workshop-note">
                Workshop variant · {m.synthesisLabel}{#if m.synthesisParents} from {m.synthesisParents}{/if}
              </span>
            {/if}
            <span class="opp-tags">
              {#if m.strength}
                {@const strength = m.strength}
                {#if m.strengthWhy}
                  <Tooltip content={m.strengthWhy} position="bottom">
                    {#snippet children()}<span class="tag tag-strength tag-{strength.variant}">{strength.label}</span>{/snippet}
                  </Tooltip>
                {:else}
                  <span class="tag tag-strength tag-{strength.variant}">{strength.label}</span>
                {/if}
              {/if}
              {#if m.angle}
                {@const angle = m.angle}
                <Tooltip content={m.angleWhy ?? ""} position="bottom">
                  {#snippet children()}<span class="tag tag-angle">{angle}</span>{/snippet}
                </Tooltip>
              {/if}
              {#if m.incumbent}
                {@const incumbent = m.incumbent}
                <Tooltip content={incumbent.full} position="bottom">
                  {#snippet children()}<span class="tag tag-parity">Incumbent: {incumbent.name}</span>{/snippet}
                </Tooltip>
              {/if}
              {#if m.risk}
                <span class="tag tag-risk">{m.risk}</span>
              {/if}
            </span>
          </span>
        </button>
        </span>

        <!-- Score -->
        <span class="cell-metric metric-score" role="cell">
          <span class="metric-num" style:color={scoreColor(m.score)}>{Math.round(m.score * 100)}</span>
        </span>

        <span class="cell-metric metric-fit" role="cell">
          <span class="metric-num fit-{m.fit.variant}">{pct(s.market_fit_score)}<span class="metric-unit">%</span></span>
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
    </div>

    {#if interactive}
      <div class="decision-rail-wrap">
        {#if selectionJourney}
          <DecisionRail
            journey={selectionJourney}
            deepResearchCost={deepCost}
            busy={poolMutationBusy || selectLoading || shortlistSaveState === "saving"}
            saveState={shortlistSaveState}
            saveError={shortlistSaveError}
            saveConflict={shortlistSaveConflict}
            researchLeadTitle={railResearchLead ? solutionDisplayTitle(railResearchLead) : ""}
            onRunRecommendation={() => {
              if (selectionDecisionState) runSelectionDecisionAction(selectionDecisionState.nextAction);
            }}
            onAddResearchLead={railResearchLead ? () => toggle(ideaKey(railResearchLead)) : undefined}
            onRemoveShortlistItem={(ideaId) => toggle(ideaId)}
            onOpenCandidates={openCandidatePool}
            onRetrySave={retryShortlistSave}
            onReloadSave={reloadShortlist}
            onEditConstraints={openFounderContext}
            onOpenCompare={() => { void goto(selectionWorkspaceHref("compare", { view: "market" })); }}
            onOpenRisks={() => { void goto(selectionWorkspaceHref("risks")); }}
            onOpenTests={() => { void goto(selectionWorkspaceHref("tests")); }}
            onOpenAlternatives={() => { void goto(selectionWorkspaceHref("alternatives")); }}
            onStartDeepResearch={handleValidate}
          />
        {:else}
          <aside class="decision-rail-fallback" aria-live="polite">
            <p class="decision-rail-fallback__eyebrow">Your decision</p>
            <h3>{selectionCount} of {MAX_SELECTIONS} shortlisted</h3>
            {#if selectionDecisionStateLoading}
              <p>Loading your next step…</p>
            {:else if selectionDecisionStateError}
              <p>{selectionDecisionStateError}</p>
              <button type="button" class="decision-rail-retry" onclick={() => { void loadSelectionDecisionState(); }}>
                Try again
              </button>
            {:else}
              <p>Choose an idea to see the next useful decision step.</p>
            {/if}
            <button
              type="button"
              class="decision-rail-start"
              disabled={!canSubmit || poolMutationBusy || selectLoading || shortlistSaveState === "saving"}
              onclick={handleValidate}
            >
              Start Deep Research
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
            <span class="variant-note-kicker">Similar candidate family · {g.ideaNames.length}</span>
            <strong>{g.sharedProduct || "Same buyer job"}</strong>
            <div class="variant-note-names" aria-label="Candidates in this family">
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
    <!-- ── Below-table IA (Phase 1b): founder-context row → verdict pull-quote →
         opportunity shape → collapsed dossier appendix. ── -->
    <DecisionBrief
      bind:this={decisionBriefRef}
      {jobId}
      profile={activeDecisionProfile}
      variant={briefVariant}
      onSaved={handleDecisionProfileSaved}
    />

    {#if summaryRecommendation}
      <section class="verdict" aria-label="Analyst verdict">
        <p class="verdict-eyebrow">{VERDICT_EYEBROW}</p>
        <p class="verdict-quote">
          <IdeaReferenceText
            content={summaryRecommendation}
            references={ideaReferences}
            onOpen={openIdeaReference}
          />
        </p>
      </section>
    {/if}

    {#if shape}
      <p class="shape-note">{shape.line}</p>
    {/if}

    {#if appendixHasContent}
      <AnalysisAppendix meta={appendixMeta} bind:expanded={appendixExpanded}>
        {#if summarySupportingNotes.length}
          <section class="appendix-notes" aria-label="Analyst notes">
            <h3 class="appendix-notes-title">Analyst notes</h3>
            {#each summarySupportingNotes as note}
              <p class="appendix-note">
                <IdeaReferenceText content={note} references={ideaReferences} onOpen={openIdeaReference} />
              </p>
            {/each}
          </section>
        {/if}
        {#if collaboratorFeedbackGroups.length > 0}
          <CollaboratorFeedback
            groups={collaboratorFeedbackGroups}
            onOpen={openDetail}
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

  {#if interactive}
    <ExperimentWorkspace
      bind:this={experimentWorkspaceRef}
      open={experimentWorkspaceOpen}
      {jobId}
      ideas={selectedIdeas.length ? selectedIdeas : solutions}
      prefill={experimentPrefill}
      {seedCost}
      narrowingDisabled={poolMutationBusy}
      onEvaluateNarrowing={handleSeed}
      onReviewNarrowing={handleReviewVariant}
      onUseNarrowing={handleUseVariant}
      onChanged={loadSelectionDecisionState}
      onOpenChallenge={selectionCount > 0 ? openChallengeFromTests : undefined}
      onClose={() => {
        experimentWorkspaceOpen = false;
        void loadSelectionDecisionState();
      }}
    />
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

  {#if !chatPanel.isOpen && !compareOpen}
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
      disabled={poolMutationBusy || !canAffordRegenerate}
      onclick={() => void handleRegenerate()}
    >
      {#if regenerating || isRegenerating}
        <Loader2 class="w-4 h-4 animate-spin" aria-hidden="true" />
        Exploring…
      {:else}
        {generateNewBatchLabel(stageCosts.regenerate_ideas)}
      {/if}
    </button>
  {/snippet}
  <FormOverlay
    open={regenerateOverlayOpen}
    size="compact"
    eyebrow="Explore alternatives"
    title="Generate more ideas"
    description="Add a small set of candidates for review. Your current ranking and shortlist stay unchanged."
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
          You need {stageCosts.regenerate_ideas} credits to generate this batch. Your current candidates are unchanged.
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
    eyebrow="Analyst suggestion"
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
          <p class="copilot-shortlist-empty">No candidates selected.</p>
        {/if}
      </section>
      <section class="copilot-shortlist-proposed">
        <p class="copilot-shortlist-label">Suggested shortlist</p>
        <ol>
          {#each copilotShortlistReview?.ideas ?? [] as idea}
            <li>{solutionDisplayTitle(idea)}</li>
          {/each}
        </ol>
      </section>
      {#if copilotShortlistReview?.rationale}
        <div class="copilot-shortlist-rationale">
          <p class="copilot-shortlist-label">Why the analyst suggested it</p>
          <p>{copilotShortlistReview.rationale}</p>
        </div>
      {/if}
      {#if copilotShortlistError}
        <p class="copilot-shortlist-error" role="alert">{copilotShortlistError}</p>
      {/if}
    </div>
  </FormOverlay>

  <DecisionCockpit
    open={compareOpen}
    initialMode={compareStartMode}
    tabGroup={groupForMode(compareStartMode)}
    initialChallengeFocus={copilotChallengeFocus}
    assumptionPrefill={copilotAssumptionPrefill}
    ownerEvidencePrefill={copilotOwnerEvidencePrefill}
    {jobId}
    ideas={comparisonIdeas}
    profile={activeDecisionProfile}
    {comparisonContext}
    shortlistedIdeaKeys={resolvedOverlapComparison ? selectedIdeaKeyList : []}
    shortlistAtCapacity={selectionCount >= MAX_SELECTIONS}
    shortlistDisabled={poolMutationBusy}
    onToggleShortlist={resolvedOverlapComparison ? toggleComparedIdea : undefined}
    variantReview={variantComparisonContext}
    onUseVariant={useReviewedVariant}
    onOpenFounderContext={() => {
      compareOpen = false;
      openFounderContext();
    }}
    onAskAnalyst={askAnalystAboutCockpit}
    onTestUnknown={handleExperimentPrefill}
    onShapeAdjacent={selectionCount >= 1 ? openForgeFromChallenge : undefined}
    {seedCost}
    onEvaluateFitReshape={handleSeed}
    onReviewFitReshape={handleReviewVariant}
    onUseFitReshape={handleUseVariant}
    onClose={() => {
      compareOpen = false;
      variantReview = null;
      overlapComparison = null;
      copilotComparisonKeys = null;
      directWorkspaceFocus = false;
      copilotChallengeFocus = null;
      copilotAssumptionPrefill = null;
      copilotOwnerEvidencePrefill = null;
      void loadSelectionDecisionState();
    }}
  />
{/if}

{#if interactive}
  <ConceptForge
    open={conceptForgeOpen}
    {jobId}
    parents={conceptForgeParents}
    prefill={copilotConceptForgePrefill}
    {seedCost}
    disabled={poolMutationBusy}
    evaluateError={seedError}
    onEvaluate={handleSeed}
    onClose={() => {
      conceptForgeOpen = false;
      conceptForgeParentKeys = null;
      copilotConceptForgePrefill = null;
    }}
  />
{/if}

<!-- Confirmation modal -->
{#if interactive}
  <SelectSolutionModal
    bind:open={modalOpen}
    solutionNames={selectedIdeas.map((solution) => solution.solution_name)}
    {solutions}
    loading={selectLoading}
    error={selectError}
    creditCost={deepCost}
    onConfirm={handleConfirmSelection}
    onCancel={handleCancelModal}
  />
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
      overlapGroups={overlapGroups ?? []}
      isSelected={selectedIdeaKeys.has(ideaKey(sortedSolutions[modalIndex]))}
      selectionIndex={selectionIndexOf(ideaKey(sortedSolutions[modalIndex]))}
      selectedCount={selectionCount}
      maxSelections={MAX_SELECTIONS}
      maxReached={selectedIdeaKeys.size >= MAX_SELECTIONS}
      disabled={selectLoading || poolMutationBusy}
      canStart={canSubmit}
      canAffordStart={canAffordDeep}
      startCost={deepCost}
      onSelect={handleToggleAdapter}
      onStartValidation={handleValidate}
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
      overlapGroups={overlapGroups ?? []}
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
  }

  /* ── Launcher: the one way back in, always the same corner ── */
  .chat-launcher {
    position: fixed;
    right: clamp(0.75rem, 2vw, 1.5rem);
    bottom: clamp(0.75rem, 2vw, 1.5rem);
    z-index: var(--z-overlay, 30);
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    min-height: 2.75rem;
    padding: 0.6rem 1rem;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border-emphasis);
    border-radius: 9999px;
    box-shadow: var(--shadow-md);
    color: var(--color-text-primary);
    font-family: var(--font-body);
    font-size: 0.8125rem;
    font-weight: 700;
    cursor: pointer;
    transition: border-color 150ms var(--selection-motion), box-shadow 150ms var(--selection-motion),
      transform 150ms var(--selection-motion);
  }
  .chat-launcher:hover {
    border-color: var(--color-accent);
    box-shadow: var(--shadow-lg);
  }
  .chat-launcher:active {
    transform: scale(0.98);
  }
  .chat-launcher:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  /* ── Analyst dock above modal overlays ──
     "Ask analyst" inside the Decision Cockpit opens the docked analyst WITHOUT
     closing the cockpit — they are designed to coexist. The dock's base layer
     (--z-overlay, 30) would otherwise sit fully under the cockpit's modal layer
     and scrim (--z-modal, 40), leaving it invisible and unclickable. Lift only
     the ANALYST dock (matched by its frame label; portaled to <body>, hence
     :global) one step above the modal layer. The expanded analyst is itself
     modal and mounts after the cockpit, so DOM order already stacks it on top. */
  :global(.workspace-overlay--docked:has(.workspace-overlay__frame[aria-label="Analyst conversation"])) {
    z-index: calc(var(--z-modal, 40) + 1);
  }

  @media (prefers-reduced-motion: reduce) {
    .chat-launcher { transition: none; }
    .chat-launcher:active { transform: none; }
  }

  .workbench {
    --selection-motion: cubic-bezier(0.32, 0.72, 0, 1);
    position: relative;
    container: selection-workbench / inline-size;
    display: flex;
    flex-direction: column;
    gap: 0.68rem;
    padding: 1rem;
    background:
      var(--color-bg-elevated);
    /* Card chrome = 1px border + shadow-sm only (Phase-1b bevel fix; slop
       guardrail 11 — no white-mix sheen/bevel shadows). */
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 52%, transparent);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
  }
  .selection-layout {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 18rem;
    gap: 1rem;
    align-items: start;
  }
  .candidate-pool {
    min-width: 0;
  }
  .decision-rail-wrap {
    position: sticky;
    top: 5.25rem;
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
    color: var(--color-accent-dark);
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
    background: var(--color-text-primary);
  }
  .decision-rail-start:disabled {
    color: var(--color-text-muted);
    background: var(--color-bg-hover);
    cursor: not-allowed;
  }
  @container selection-workbench (max-width: 72rem) {
    .selection-layout {
      grid-template-columns: 1fr;
    }
    .decision-rail-wrap {
      position: static;
      grid-row: 2;
    }
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
    border-radius: 0;
  }
  .cmd.cmd-owner { grid-template-columns: minmax(0, 1fr); }
  .cmd-title {
    margin: 0;
    max-width: 42ch;
    font-family: var(--font-display);
    font-size: 1rem;
    font-weight: 800;
    line-height: 1.2;
    letter-spacing: 0;
    color: var(--color-text-primary);
    text-wrap: balance;
  }
  .cmd-sub {
    margin: 0.14rem 0 0;
    max-width: 68ch;
    font-size: 0.75rem;
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
    font-size: 0.6875rem;
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
    font-size: 1.5rem;
    font-weight: 800;
    line-height: 1;
    color: var(--color-text-primary);
    font-variant-numeric: tabular-nums;
  }
  .vote-tally-label {
    font-size: 0.6875rem;
    font-weight: 700;
    color: var(--color-text-muted);
  }
  .vote-tally-hint {
    margin: 0;
    max-width: 13rem;
    justify-self: end;
    font-size: 0.75rem;
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
    border-radius: 0.625rem;
  }
  .regen-focus-btn {
    padding: 0.32rem 0.55rem;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 0.375rem;
    color: var(--color-text-secondary);
    font-family: var(--font-body);
    font-size: 0.75rem;
    font-weight: 700;
    cursor: pointer;
    transition:
      transform 220ms var(--selection-motion),
      border-color 220ms var(--selection-motion),
      color 220ms var(--selection-motion),
      background 220ms var(--selection-motion);
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
    font-size: 0.875rem;
    line-height: 1.5;
    text-wrap: pretty;
  }
  /* ── Verdict pull-quote + shape line (DESIGN_SYSTEM §5.7) ── */
  .verdict {
    display: grid;
    gap: 0.5rem;
    margin: 0.35rem 0 0;
  }
  /* `.verdict-eyebrow`, NOT `.verdict-label` — the latter is a display-3xl
     global in components.css (§11 collision note). */
  .verdict-eyebrow {
    margin: 0;
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .verdict-quote {
    max-width: 74ch;
    margin: 0;
    color: var(--color-text-primary);
    font-family: var(--font-display);
    font-size: 1rem;
    font-weight: 600;
    line-height: 1.45;
    letter-spacing: -0.01em;
    text-wrap: pretty;
  }
  .verdict-quote :global(button.idea-reference-link) {
    color: inherit;
    font: inherit;
    text-decoration-color: var(--color-border-emphasis);
    text-decoration-line: underline;
    text-decoration-style: dotted;
    text-decoration-thickness: 1px;
    text-underline-offset: 0.18em;
    transition: color 160ms ease, text-decoration-color 160ms ease;
  }
  .verdict-quote :global(button.idea-reference-link:hover) {
    color: var(--color-accent-dark);
    text-decoration-color: currentColor;
  }
  .shape-note {
    max-width: 74ch;
    margin: 0;
    color: var(--color-text-secondary);
    font-size: 0.75rem;
    line-height: 1.5;
  }

  /* ── Appendix: analyst supporting notes ── */
  .appendix-notes {
    display: grid;
    gap: 0.55rem;
    padding: 0.15rem 0.05rem 0;
  }
  .appendix-notes-title {
    margin: 0;
    color: var(--color-text-secondary);
    font-size: 0.75rem;
    font-weight: 600;
  }
  .appendix-note {
    max-width: 72ch;
    margin: 0;
    color: var(--color-text-secondary);
    font-size: 0.8125rem;
    line-height: 1.58;
    text-wrap: pretty;
  }
  .appendix-note :global(button.idea-reference-link) {
    color: inherit;
    font-weight: 600;
    text-decoration-color: var(--color-border-emphasis);
    text-decoration-line: underline;
    text-decoration-style: dotted;
    text-decoration-thickness: 1px;
    text-underline-offset: 0.18em;
    transition: color 160ms ease, text-decoration-color 160ms ease;
  }
  .appendix-note :global(button.idea-reference-link:hover) {
    color: var(--color-accent-dark);
    text-decoration-color: currentColor;
  }

  .regen-error {
    margin: 0;
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: var(--color-error-text);
    text-align: right;
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
    font-size: 0.8125rem;
    line-height: 1.4;
  }
  .seed-banner--accepted {
    border-color: color-mix(in srgb, var(--color-success) 30%, transparent);
    background: color-mix(in srgb, var(--color-success) 6%, var(--color-bg-surface));
    color: var(--color-success-text);
  }

  /* Momentary landing highlight for a settled seed — the row it scrolls to. */
  .row-seed-highlight {
    animation: seed-row-flash 2.4s ease-out;
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
    background: var(--color-bg-surface);
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 56%, transparent);
    border-radius: 0.5rem;
  }
  .row {
    display: grid;
    grid-template-columns: 1.35rem 5.65rem minmax(0, 1fr) 4rem 4.55rem 4.7rem 5.2rem;
    align-items: center;
    gap: 0.56rem;
    padding: 0.56rem 0.68rem;
    border: 0;
    border-top: 1px solid var(--color-border);
    border-radius: 0;
    background: var(--color-bg-elevated);
    box-shadow: none;
    transition:
      background 280ms var(--selection-motion),
      box-shadow 280ms var(--selection-motion);
  }
  .row-head {
    min-height: 1.75rem;
    padding: 0.4rem 0.7rem;
    border: 0;
    border-bottom: 1px solid color-mix(in srgb, var(--color-border-emphasis) 42%, transparent);
    border-radius: 0;
    background: color-mix(in srgb, var(--color-bg-surface) 74%, var(--color-bg-elevated));
    box-shadow: none;
  }
  .row:not(.row-head):hover {
    background: color-mix(in srgb, var(--color-bg-surface) 48%, var(--color-bg-elevated));
  }
  .row-sel {
    background: color-mix(in srgb, var(--color-accent) 3%, var(--color-bg-elevated));
    box-shadow: inset 2px 0 0 color-mix(in srgb, var(--color-accent) 58%, var(--color-border-emphasis));
  }
  .row-maxed { opacity: 1; }

  /* Role-only wrapper: carries columnheader/rowheader semantics for an
     interactive cell without introducing a box, so the button underneath
     stays a direct grid item of .row. */
  .cell-shell {
    display: contents;
  }

  .cell-rank {
    font-family: var(--font-mono);
    font-size: 0.8125rem;
    font-weight: 700;
    color: var(--color-text-muted);
    font-variant-numeric: tabular-nums;
    text-align: center;
  }
  /* Mono uppercase header, matching the dashboard list-head "hardware" label. */
  .row-head .cell-rank,
  .row-head .cell-select-label,
  .row-head .cell-title-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    line-height: 1;
    color: var(--color-text-secondary);
  }
  .row-head .cell-title-label { padding-left: 0; }

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
    border-radius: 0.375rem;
    border: 1px solid var(--color-input-border);
    background: var(--color-bg-elevated);
    color: var(--color-text-muted);
    cursor: pointer;
    font-family: var(--font-body);
    font-size: 0.6875rem;
    font-weight: 700;
    transition:
      transform 220ms var(--selection-motion),
      border-color 220ms var(--selection-motion),
      background 220ms var(--selection-motion),
      color 220ms var(--selection-motion);
  }
  .select-control:hover:not(.maxed) {    border-color: var(--color-accent);
    color: var(--color-accent-dark);
    background: color-mix(in srgb, var(--color-accent) 5%, var(--color-bg-elevated));
  }
  .select-control.sel {
    border-color: color-mix(in srgb, var(--color-accent) 54%, var(--color-border-emphasis));
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
    width: 0.94rem;
    height: 0.94rem;
    border-radius: 0.25rem;
    border: 1.25px solid currentColor;
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
  .select-check {
    width: 0.7rem;
    height: 0.7rem;
    stroke-width: 2.5;
  }
  .row:has(.cell-select input:focus-visible) .select-control {
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
    border-radius: 0.5rem;
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
    font-size: 0.625rem;
    font-style: italic;
    font-weight: 600;
    line-height: 1.2;
    white-space: nowrap;
  }
  .opp-title {
    font-family: var(--font-display);
    font-size: 0.8125rem;
    font-weight: 700;
    line-height: 1.2;
    color: var(--color-text-primary);
    transition: color 0.15s ease;
    text-wrap: pretty;
  }
  .opp-summary {
    max-width: 72ch;
    font-size: 0.75rem;
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
    font-size: 0.6875rem;
    line-height: 1.36;
    color: var(--color-text-muted);
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
    font-size: 0.6875rem;
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
    border-radius: 0.375rem;
    font-family: var(--font-body);
    font-size: 0.6875rem;
    font-weight: 700;
    letter-spacing: 0;
    line-height: 1.18;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .tag-strength { border: 1px solid currentColor; }
  .tag-success {
    background: color-mix(in srgb, var(--color-success) 9%, transparent);
    color: var(--color-success-dark);
  }
  .tag-accent {
    background: var(--color-accent-subtle);
    color: var(--color-accent-dark);
  }
  .tag-info {
    background: var(--color-bg-surface);
    color: var(--color-text-secondary);
  }
  .tag-warning {
    background: color-mix(in srgb, var(--color-warning) 11%, transparent);
    color: var(--color-warning-text);
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
    font-size: 0.625rem;
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
    border-radius: 0.4rem;
    background: color-mix(in srgb, var(--color-accent) 4%, var(--color-bg-surface));
  }
  .variant-note-copy {
    display: grid;
    gap: 0.22rem;
    min-width: 0;
  }
  .variant-note-copy > strong {
    color: var(--color-text-primary);
    font-size: 0.8125rem;
    line-height: 1.25;
  }
  .variant-note-kicker {
    font-family: var(--font-mono);
    color: var(--color-text-secondary);
    font-size: 0.625rem;
    font-weight: 700;
    letter-spacing: 0.055em;
    text-transform: uppercase;
  }
  .variant-note-names {
    display: flex;
    flex-wrap: wrap;
    gap: 0.22rem 0.5rem;
    color: var(--color-text-secondary);
    font-size: 0.72rem;
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
    border-radius: 0.55rem;
    background: var(--color-bg-elevated);
    color: var(--color-text-primary);
    font-size: 0.75rem;
    font-weight: 700;
    white-space: nowrap;
    cursor: pointer;
    transition: transform 180ms ease, border-color 180ms ease, color 180ms ease;
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
    font-size: 0.6875rem;
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
    color: var(--color-text-muted);
    background: transparent;
    border: none;
    cursor: pointer;
    min-height: 1.5rem;
    padding: 0.16rem 0;
    border-radius: 0.375rem;
    transition:
      color 180ms var(--selection-motion),
      transform 180ms var(--selection-motion);
  }
  .cell-metric-head:hover {    color: var(--color-text-secondary);
  }
  .cell-metric-head.active { color: var(--color-accent-dark); }
  @media (prefers-reduced-motion: reduce) {
    .cell-metric-head { transition: none; }
  }
  .metric-num {
    font-family: var(--font-mono);
    font-size: 0.8125rem;
    font-weight: 800;
    color: var(--color-text-primary);
    line-height: 1;
  }
  .metric-unit {
    font-size: 0.625rem;
    font-weight: 600;
    color: var(--color-text-muted);
    margin-left: 0.05rem;
  }
  .fit-success { color: var(--color-success-dark); }
  .fit-warning { color: var(--color-text-primary); }
  .fit-muted { color: var(--color-text-muted); }
  .metric-score { align-items: flex-end; }
  .metric-score .metric-num { font-size: 0.9375rem; }
  .metric-build-num {
    max-width: 5.8rem;
    font-size: 0.75rem;
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
    border-radius: 0.75rem;
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
    font-size: 0.6875rem;
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
    font-size: 0.875rem;
    font-weight: 600;
    line-height: 1.4;
  }
  .copilot-shortlist-empty,
  .copilot-shortlist-rationale p,
  .copilot-shortlist-error { margin: 0; }
  .copilot-shortlist-empty,
  .copilot-shortlist-rationale p {
    color: var(--color-text-secondary);
    font-size: 0.8125rem;
    line-height: 1.5;
  }
  .copilot-shortlist-rationale {
    grid-column: 1 / -1;
    padding-top: 0.25rem;
  }
  .copilot-shortlist-error {
    grid-column: 1 / -1;
    color: var(--color-error-text);
    font-size: 0.8125rem;
  }
  .copilot-shortlist-cancel,
  .copilot-shortlist-apply {
    min-height: 2.75rem;
    padding: 0.65rem 1rem;
    border-radius: 0.65rem;
    font-weight: 700;
    cursor: pointer;
  }
  .copilot-shortlist-cancel {
    border: 1px solid var(--color-border-emphasis);
    background: var(--color-bg-elevated);
    color: var(--color-text-primary);
  }
  .copilot-shortlist-apply {
    border: 1px solid var(--color-text-primary);
    background: var(--color-text-primary);
    color: var(--color-bg-elevated);
  }
  .copilot-shortlist-apply:disabled {
    background: var(--color-bg-hover);
    color: var(--color-text-muted);
    cursor: wait;
  }
  /* ── Responsive ── */
  @media (max-width: 859px) {
    .workbench { padding: 0.88rem 0.88rem 1.25rem; }
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
    .row {
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
      border-radius: 0;
    }
    .row-head { display: none; }
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
      font-size: 0.6875rem;
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
      font-size: 0.75rem;
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
    .cmd-sub { font-size: 0.8125rem; }
    .regen-focus-btn {
      padding: 0.3rem 0.46rem;
      font-size: 0.6875rem;
    }
  }

</style>
