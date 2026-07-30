<script lang="ts">
  import { untrack } from "svelte";
  import { page } from "$app/state";
  import { goto, invalidateAll } from "$app/navigation";
  import {
    subscribeToProgress,
    shouldKeepSSEOpen,
    getReportSummary,
    getDiscoveryShareStatus,
    regenerateIdeas,
    ApiError,
  } from "$lib/api";
  import type { DiscoveryVoteRationale } from "$lib/api";
  import Badge from "$lib/components/ui/Badge.svelte";
  import PageHeader from "$lib/components/ui/PageHeader.svelte";
  import {
    Loader2,
    AlertTriangle,
    CheckCircle,
    ArrowRight,
    Telescope,
    RotateCw,
    Package,
    Share2,
    BarChart3,
    Copy,
  } from "lucide-svelte";
  import { creditTopUp } from "$lib/stores/creditTopUp.svelte";
  import { chatLedger } from "$lib/stores/chatLedger.svelte";
  import { getAdjustedStageCounts } from "$lib/utils/stages";
  import type { Job, SolutionPreview, ReportSummary } from "$lib/types/job";
  import Button from "$lib/components/ui/Button.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";
  import SelectedSolutionsSummary from "$lib/components/SelectedSolutionsSummary.svelte";
  import DeliverableRow from "$lib/components/job/DeliverableRow.svelte";
  import JobHeroAside from "$lib/components/job/JobHeroAside.svelte";

  // Preview / Dashboard components
  import PhaseNav from "$lib/components/nav/PhaseNav.svelte";
  import TourHost from "$lib/tour/TourHost.svelte";
  import TourRestartButton from "$lib/tour/TourRestartButton.svelte";
  import ExpandableSection from "$lib/components/ui/ExpandableSection.svelte";
  import PreviewOverview from "$lib/components/preview/PreviewOverview.svelte";
  import ProgressStepper from "$lib/components/preview/ProgressStepper.svelte";
  import PainPointSummaryCard from "$lib/components/preview/PainPointSummaryCard.svelte";
  import AudienceSnapshot from "$lib/components/preview/AudienceSnapshot.svelte";
  import CommunitySourcesSection from "$lib/components/preview/CommunitySourcesSection.svelte";
  import SelectionWorkbench from "$lib/components/selection/SelectionWorkbench.svelte";
  import type { SelectionJourneyTask } from "$lib/selection/decisionJourney";
  import { SHORTLIST_TITLE } from "$lib/selection/labels";
  import GateWorkbench from "$lib/components/gate/GateWorkbench.svelte";
  import ResearchProgressScreen from "$lib/components/preview/ResearchProgressScreen.svelte";

  import SEOKeywordsPreview from "$lib/components/preview/SEOKeywordsPreview.svelte";
  import MarketSnapshot from "$lib/components/preview/MarketSnapshot.svelte";
  import DiscoveryEvidence from "$lib/components/discovery/DiscoveryEvidence.svelte";
  import AudienceSection from "$lib/components/sections/AudienceSection.svelte";
  import UnifiedHero from "$lib/components/sections/UnifiedHero.svelte";
  import NicheRealityCheck from "$lib/components/sections/NicheRealityCheck.svelte";
  import Competitors from "$lib/components/sections/Competitors.svelte";
  import { LOCKED_PREVIEW_SECTIONS } from "$lib/types/previewReport";
  import {
    placeholderExecutiveDashboard,
    placeholderCompetitors,
  } from "$lib/data/previewPlaceholders";
  import { stripLeadingArticle, titleCase } from "$lib/utils/format";
  import { STAGE_MAP, REPORT_ICON } from "$lib/config/billable-stages";
  import { getSolutions } from "$lib/api";
  import AnnotationProvider from "$lib/components/annotations/AnnotationProvider.svelte";
  import ShareDiscoveryModal from "$lib/components/ShareDiscoveryModal.svelte";
  import type { DiscoveryData } from "$lib/types/discovery";
  import type { PreviewReport } from "$lib/types/previewReport";
  import { getDiscoveryData, getPreviewReport } from "$lib/api";
  import { createDiscoveryDisplayModel } from "$lib/discovery/discoveryDisplay";
  import { normalizeSolutionPreviews } from "$lib/utils/displayGuards";
  import { setServedCapThresholds } from "$lib/utils/scoreRationale";
  import { createHubDraftRefreshGuard } from "./hubDraftRefresh";

  let { data } = $props();

  // Backend-served market-fit cap thresholds → score-hint copy (drift-proof against
  // env overrides). One-time init is enough: values are static per deployment, and
  // page init runs before SelectionWorkbench/SolutionDetail derive any hint.
  // svelte-ignore state_referenced_locally -- intentional one-time capture
  setServedCapThresholds(data.metricExplanations?.capThresholds ?? null);

  // Multi-tab draft parity (mirrors selection/+layout.svelte): refresh the hub when a
  // draft-PUT broadcast from another tab carries a newer selectionDraft version.
  const draftRefreshGuard = createHubDraftRefreshGuard(() => void invalidateAll());

  // ── Server data (reactive via $derived, updates on navigation/invalidateAll) ──
  const serverJob = $derived(data.job as Job | null);
  const serverSolutions = $derived((data.solutions ?? null) as SolutionPreview[] | null);
  const serverReportSummary = $derived((data.reportSummary ?? null) as ReportSummary | null);
  const serverDiscoveryData = $derived((data.discoveryData ?? null) as DiscoveryData | null);
  const serverSolutionVotes = $derived((data.solutionVotes ?? {}) as Record<string, number>);
  const serverSolutionVotesById = $derived((data.solutionVotesById ?? {}) as Record<string, number>);
  const serverVoteRationales = $derived((data.voteRationales ?? []) as DiscoveryVoteRationale[]);
  const serverPreviewReport = $derived((data.previewReport ?? null) as PreviewReport | null);

  // ── Client overrides (SSE updates, async fetches) ──
  let clientJob = $state<Job | null>(null);
  // Emitted up from SelectionWorkbench so the sidebar renders the same two
  // primary decision tools + status the launchpad shows (one status source).
  let selectionToolTasks = $state<SelectionJourneyTask[] | undefined>(undefined);
  let liveShortlist = $state<{ jobId: string; count: number } | null>(null);
  let clientSolutions = $state<SolutionPreview[] | null>(null);
  let clientReportSummary = $state<ReportSummary | null>(null);
  let clientDiscoveryData = $state<DiscoveryData | null>(null);
  let clientSolutionVotes = $state<Record<string, number> | null>(null);
  let clientPreviewReport = $state<PreviewReport | null>(null);
  let clientSolutionVotesById = $state<Record<string, number> | null>(null);
  let clientVoteRationales = $state<DiscoveryVoteRationale[] | null>(null);
  let clientInvalidSolutionCount = $state<number | null>(null);
  let clientDiscoveryFetchFailed = $state(false);
  let clientPreviewReportFetchFailed = $state(false);

  // ── Merged: client overrides take precedence over server data ──
  const job = $derived(clientJob ?? serverJob);

  // Human-readable run timestamp (drops seconds; month name over machine locale).
  function formatRunDate(iso: string): string {
    const d = new Date(iso);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
      + " at " + d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  }
  const runTimeline = $derived.by(() => {
    // startedAt/completedAt track the MOST RECENT operation, not the whole job.
    // During selection that may be Discovery, an added batch, or a branched-direction
    // evaluation, so naming it "Discovery run" becomes false after either idea update.
    const parts = [job?.status === "COMPLETED" ? "Deep Research run" : "Latest research activity"];
    if (job?.startedAt) parts.push(`started ${formatRunDate(job.startedAt)}`);
    if (job?.completedAt) parts.push(`completed ${formatRunDate(job.completedAt)}`);
    return parts.join(" · ");
  });
  let copiedRunId = $state(false);
  let copiedRunIdTimer: ReturnType<typeof setTimeout> | undefined;
  async function copyRunId() {
    if (!job) return;
    try {
      await navigator.clipboard.writeText(job.id);
      copiedRunId = true;
      clearTimeout(copiedRunIdTimer);
      copiedRunIdTimer = setTimeout(() => (copiedRunId = false), 1600);
    } catch {
      /* clipboard unavailable — no-op */
    }
  }
  // Hidden-stage-adjusted counts so the aside matches the dashboard's in-progress
  // rows and the progress screen (see $lib/utils/stages).
  const jobStageCounts = $derived(
    job ? getAdjustedStageCounts(job) : { completed: 0, total: 0 },
  );
  const localSolutions = $derived(clientSolutions ?? serverSolutions);
  const reportSummary = $derived(clientReportSummary ?? serverReportSummary);
  const discoveryData = $derived(clientDiscoveryData ?? serverDiscoveryData);
  const solutionVotes = $derived(clientSolutionVotes ?? serverSolutionVotes);
  const previewReport = $derived(clientPreviewReport ?? serverPreviewReport);
  const completedEvidenceLimited = $derived.by(() => {
    const quality = previewReport?.data_quality_summary?.overall_data_quality?.trim().toLowerCase();
    return quality === "low" || (previewReport?.data_quality_summary?.quality_caveats?.length ?? 0) > 0;
  });
  const completedVerdict = $derived.by(() => {
    const normalized = reportSummary?.verdict?.trim().toUpperCase().replace(/[\s_]+/g, "-");
    if (normalized === "GO") {
      return {
        label: completedEvidenceLimited ? "Go · evidence-limited" : "Go",
        tone: completedEvidenceLimited ? "caution" : "positive",
      } as const;
    }
    if (normalized === "CONDITIONAL" || normalized === "MAYBE") {
      return { label: "Conditional", tone: "caution" } as const;
    }
    if (normalized === "NO-GO" || normalized === "NO" || normalized === "NOGO") {
      return { label: "No-go", tone: "negative" } as const;
    }
    return null;
  });
  const invalidSolutionCount = $derived(
    clientInvalidSolutionCount ?? Number(data.invalidSolutionCount ?? 0),
  );
  const discoveryFetchFailed = $derived(
    !discoveryData && (clientDiscoveryFetchFailed || Boolean(data.discoveryDataFetchFailed)),
  );
  const previewFetchFailed = $derived(
    !previewReport && (clientPreviewReportFetchFailed || Boolean(data.previewReportFetchFailed)),
  );

  const solutionVotesById = $derived(clientSolutionVotesById ?? serverSolutionVotesById);
  const voteRationales = $derived(clientVoteRationales ?? serverVoteRationales);
  // ── Pure local state (UI-only) ──
  let loading = $state(false);
  let error = $state("");
  let unsubscribeSSE: (() => void) | null = null;
  let cancelling = $state(false);
  let cancelError = $state("");
  let isResuming = $state(false);
  let resumeError = $state("");
  let generatingLanding = $state(false);
  let landingError = $state("");
  let summaryFetched = false;
  let discoveryShareOpen = $state(false);
  let discoveryShareTrigger = $state<HTMLButtonElement>();
  let discoveryLoading = $state(false);
  let lastHandledStatus = $state('');
  // apply_stay round-trips can re-arrive at the SAME gate (status stays
  // AWAITING_GATE the whole time) — gateReachedAt is the only signal that a
  // fresh artifact landed, so the chat-reload effect below tracks it too.
  let lastGateReachedAt = $state<string | null>(null);
  // Solutions fetch state for the AWAITING_SELECTION empty state (0 candidates) —
  // distinguishes "still loading" from "fetch failed" from "genuinely zero".
  let solutionsLoading = $state(false);
  let solutionsFetchFailed = $state(false);
  let solutionsFetchAttempted = $state(false);
  let regeneratingFromEmpty = $state(false);
  let regenerateFromEmptyError = $state("");
  let regenerateFromEmptyClientRequestId = $state(crypto.randomUUID());

  const jobId = $derived(page.params.jobId);
  const regenerateFromEmptyCost = $derived(
    (page.data.stageCosts as { regenerate_ideas?: number } | undefined)?.regenerate_ideas ?? 0,
  );
  // A durable seed receipt normally identifies this round-trip. The active
  // dispatch is the stronger fallback when receipt hydration lags or failed:
  // a queued seed must not become "Deep Research" merely because the owner
  // already has a saved shortlist.
  const seedPending = $derived(
    job?.activeDispatchKind === 'SEED_IDEA'
    || (
      chatLedger.jobId === jobId
      && (
        chatLedger.hasPendingSeed
        || chatLedger.activeOperation?.kind === 'SEED_IDEA'
      )
    )
  );
  const seedRunning = $derived(
    seedPending && ['QUEUED', 'RUNNING'].includes(job?.status ?? '')
  );
  const sidebarSelectedCount = $derived(
    liveShortlist && liveShortlist.jobId === jobId
      ? liveShortlist.count
      : job?.selectionDraft?.items.length
        ?? job?.selectedSolutionIds?.length
        ?? job?.selectedSolutions?.length
        ?? 0,
  );

  const isInteractiveStatus = $derived(
    job
      ? [
          "AWAITING_SELECTION",
          "REGENERATING",
          "RUNNING_PHASE2",
        ].includes(job.status)
      : false,
  );
  const failedCatalogDeepResearch = $derived(
    job?.status === "FAILED" && job.entryMode === "deep_idea",
  );
  const failedDuringDeepResearch = $derived(
    job?.status === "FAILED"
    && job.jobMode === "interactive"
    && job.entryMode !== "deep_idea"
    && (
      (job.selectedSolutionIds?.length ?? 0) > 0
      || (job.selectedSolutions?.length ?? 0) > 0
    ),
  );

  const isRegenQueued = $derived(
    job?.status === 'QUEUED' &&
    !seedRunning &&
    job?.activeDispatchKind === 'REGENERATE'
  );
  const isQueuedPhase2 = $derived(
    job?.status === 'QUEUED'
    && !seedRunning
    && (
      job.activeDispatchKind === 'DEEP_RESEARCH'
      || (
        job.activeDispatchKind == null
        && (
          job.entryMode === 'deep_idea'
          || (
            job.jobMode === 'interactive'
            && (
              (job.selectionDraft?.items.length ?? 0) > 0
              || (job.selectedSolutionIds?.length ?? 0) > 0
              || (job.selectedSolutions?.length ?? 0) > 0
            )
          )
        )
      )
    )
  );

  // Guided-mode (Phase B) gate: gate-action('apply_stay') flips the job through
  // AWAITING_GATE -> QUEUED -> RUNNING -> AWAITING_GATE (refreshed) — a real status
  // change, but a SHORT round-trip that should keep GateWorkbench mounted (with its
  // own refresh-skeleton) rather than handing off to the full progress screen. Only
  // GateWorkbench's own apply_stay call sets this; gate-action('continue') never does
  // (it's a genuine resume, so it SHOULD hand off to ResearchProgressScreen). It's
  // cleared on the happy path by the AWAITING_GATE effect below, and on EVERY
  // apply_stay failure (cap 409, concurrency conflict, compensation, network) by
  // GateWorkbench's onApplyStayError — otherwise a failed apply would leave this
  // stuck true and a later successful Continue would keep GateWorkbench mounted
  // instead of handing off to the progress screen.
  let gateApplyPending = $state(false);
  const applyStayActive = $derived(
    job?.activeDispatchKind === 'APPLY_STAY'
    && ['QUEUED', 'RUNNING'].includes(job?.status ?? '')
  );
  const isGatePhase = $derived(
    job?.status === 'AWAITING_GATE' ||
    applyStayActive ||
    (gateApplyPending && ['QUEUED', 'RUNNING'].includes(job?.status ?? ''))
  );

  // Use local solutions (updated via SSE) or fall back to job data
  const displaySolutions = $derived(
    localSolutions ?? job?.solutionIdeas ?? [],
  );

  function connectSSE() {
    unsubscribeSSE?.();
    if (!jobId) return;
    const currentJob = untrack(() => job);
    if (currentJob && !shouldKeepSSEOpen(currentJob)) return;

    unsubscribeSSE = subscribeToProgress(
      jobId,
      (sseData) => {
        // Another tab saved the shortlist: refresh before an edit here 409s. Own
        // saves are excluded — SelectionWorkbench reports its bumped version up
        // (onShortlistVersionChange) before this callback sees the broadcast.
        draftRefreshGuard.handleSsePayload(sseData as Job | null);
        if (sseData && sseData.id) {
          // Progress events are intentionally partial. Replacing the job here drops
          // the saved shortlist, dossier metadata, and other selection-only fields
          // for the duration of a seed evaluation.
          clientJob = {
            ...(clientJob ?? serverJob),
            ...sseData,
          } as Job;
          if (sseData.solutionIdeas) {
            const normalized = normalizeSolutionPreviews(sseData.solutionIdeas);
            clientSolutions = normalized.solutions;
            clientInvalidSolutionCount = normalized.invalidCount;
          }
        }
      },
      (err) => console.warn("SSE error:", err.message),
      {},
    );
  }

  async function pollVotes(id: string) {
    try {
      const info = await getDiscoveryShareStatus(id);
      clientSolutionVotes = info.isShared ? info.solutionVotes ?? {} : {};
      clientSolutionVotesById = info.isShared ? info.solutionVotesById ?? {} : {};
      clientVoteRationales = info.isShared ? info.voteRationales ?? [] : [];
    } catch {}
  }

  async function loadDiscoveryData(id: string) {
    if (discoveryLoading) return;
    discoveryLoading = true;
    try {
      clientDiscoveryData = await getDiscoveryData(id);
      clientDiscoveryFetchFailed = false;
    } catch {
      clientDiscoveryFetchFailed = true;
    }
    finally { discoveryLoading = false; }
  }

  let previewReportLoading = $state(false);
  async function loadPreviewReport(id: string) {
    if (previewReportLoading) return;
    previewReportLoading = true;
    try {
      clientPreviewReport = await getPreviewReport(id);
      clientPreviewReportFetchFailed = false;
    } catch {
      clientPreviewReportFetchFailed = true;
    }
    finally { previewReportLoading = false; }
  }

  // AWAITING_SELECTION solutions fetch — shared by the SSE status-transition
  // effect, the initial-load auto-fetch, and the empty-state Retry button, so
  // "loading" / "fetch failed" / "genuinely zero" stay distinguishable everywhere.
  async function fetchSolutions() {
    if (!jobId || solutionsLoading) return;
    solutionsLoading = true;
    solutionsFetchFailed = false;
    try {
      const d = await getSolutions(jobId);
      const normalized = normalizeSolutionPreviews(d.solutionIdeas);
      clientSolutions = normalized.solutions;
      clientInvalidSolutionCount = normalized.invalidCount;
      if (job) {
        clientJob = {
          ...job,
          selectionDraft: d.selectionDraft,
          canRegenerate: d.canRegenerate,
          ideaBatchCompletedCount: d.ideaBatchCompletedCount,
          maxIdeaBatches: d.maxIdeaBatches,
        };
      }
    } catch {
      solutionsFetchFailed = true;
      // Fall back to whatever the job object already carries (e.g. from SSE)
      // rather than leaving clientSolutions stuck on a stale null.
      const normalized = normalizeSolutionPreviews(job?.solutionIdeas);
      clientSolutions = normalized.solutions.length > 0
        ? normalized.solutions
        : clientSolutions;
      clientInvalidSolutionCount = normalized.invalidCount;
    } finally {
      solutionsLoading = false;
      solutionsFetchAttempted = true;
    }
  }

  async function retryDiscoveryDossier(): Promise<void> {
    if (!jobId) return;
    await Promise.all([
      discoveryFetchFailed ? loadDiscoveryData(jobId) : Promise.resolve(),
      previewFetchFailed ? loadPreviewReport(jobId) : Promise.resolve(),
    ]);
  }

  // Append-only batch action for the AWAITING_SELECTION zero-candidates case — same
  // operation as SelectionWorkbench's action, just without
  // a ranked set to attach it to.
  async function regenerateFromEmpty() {
    if (!job || !jobId || regeneratingFromEmpty || costsUnavailable) return;
    regeneratingFromEmpty = true;
    regenerateFromEmptyError = "";
    try {
      const response = await regenerateIdeas(jobId, {
        clientRequestId: regenerateFromEmptyClientRequestId,
        expectedCost: regenerateFromEmptyCost,
        idea_focus: "auto",
      });
      regenerateFromEmptyClientRequestId = crypto.randomUUID();
      chatLedger.markBatchPending(response.operationId, {
        ordinal: response.batchOrdinal,
        focus: response.focus ?? "auto",
      });
      clientJob = { ...job, status: 'QUEUED', activeDispatchKind: 'REGENERATE' };
      void invalidateAll();
    } catch (e) {
      if (e instanceof ApiError && e.status === 402) {
        const body = e.details as { balance?: number; required?: number } | undefined;
        creditTopUp.show({
          balance: body?.balance ?? (page.data.creditBalance as number) ?? 0,
          required: body?.required ?? (page.data.stageCosts as any)?.regenerate_ideas ?? 0,
          stageName: "additional idea batch",
        });
      } else if (
        e instanceof ApiError
        && e.status === 409
        && (e.details as { code?: string } | undefined)?.code === "PRICE_CHANGED"
      ) {
        await invalidateAll();
        regenerateFromEmptyError = "The idea batch price changed. Review the updated cost and try again.";
      } else {
        regenerateFromEmptyError = e instanceof Error ? e.message : "Failed to generate ideas";
      }
    } finally {
      regeneratingFromEmpty = false;
    }
  }

  async function refreshJob() {
    try {
      const res = await fetch(`/api/jobs/${jobId}`);
      if (!res.ok) throw new Error('Failed to refresh');
      clientJob = await res.json();
    } catch (e) {
      console.warn('Job refresh failed:', e);
    }
  }

  async function resumeJob() {
    if (!job || isResuming || (failedCatalogDeepResearch && costsUnavailable)) return;
    isResuming = true;
    resumeError = "";
    try {
      const resumePayload = failedCatalogDeepResearch
        ? { expectedCost: deepResearchStageCost }
        : {};
      const res = await fetch(`/api/jobs/${jobId}/resume`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(resumePayload),
      });
      if (!res.ok) {
        const data = await res.json();
        if (res.status === 409 && data.code === "PRICE_CHANGED") {
          await invalidateAll();
          throw new Error("The Deep Research price changed. Review the updated cost and try again.");
        }
        throw new Error(data.error || "Failed to resume job");
      }
      const data = await res.json();
      if (data.status === "AWAITING_SELECTION") {
        await goto(`/jobs/${jobId}#opportunities`, {
          replaceState: true,
          invalidateAll: true,
        });
        return;
      }
      const updatedProgress = (job.progress ?? []).map((stage) =>
        stage.status === "FAILED" || stage.status === "RUNNING"
          ? { ...stage, status: "PENDING" as const }
          : stage,
      );
      clientJob = { ...job, status: "QUEUED", errorMessage: null, progress: updatedProgress };
      connectSSE();
      if (data.creditCharged) invalidateAll();
    } catch (e) {
      resumeError = e instanceof Error ? e.message : "Failed to resume job";
    } finally {
      isResuming = false;
    }
  }

  async function generateLanding() {
    if (!job || generatingLanding || costsUnavailable) return;
    generatingLanding = true;
    landingError = "";
    try {
      const res = await fetch(`/api/jobs/${jobId}/generate-landing`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expectedCost: landingStageCost }),
      });
      if (!res.ok) {
        const data = await res.json();
        if (res.status === 402 && data.code === "INSUFFICIENT_CREDITS") {
          creditTopUp.show({
            balance: data.balance ?? (page.data.creditBalance as number) ?? 0,
            required: landingStageCost,
            stageName: "landing page",
          });
          generatingLanding = false;
          return;
        }
        if (res.status === 409 && data.code === "PRICE_CHANGED") {
          await invalidateAll();
          throw new Error("The landing page price changed. Review the updated cost and try again.");
        }
        throw new Error(data.error || "Failed to generate landing page");
      }
      invalidateAll();
      await refreshJob();
      connectSSE();
    } catch (e) {
      landingError = e instanceof Error ? e.message : "Failed to generate landing page";
    } finally {
      generatingLanding = false;
    }
  }

  async function cancelJob() {
    if (!job || cancelling) return;
    cancelling = true;
    cancelError = "";
    try {
      const res = await fetch(`/api/jobs/${jobId}/cancel`, { method: "POST" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.error || "Failed to cancel job");
      }
      clientJob = {
        ...job,
        status: "CANCELLED",
        errorMessage: "Cancelled by user",
        creditRefunded: Number(data.creditRefunded ?? 0) > 0,
      };
      unsubscribeSSE?.();
    } catch (e) {
      cancelError = e instanceof Error ? e.message : "Failed to cancel job";
    } finally {
      cancelling = false;
    }
  }

  // Clear client overrides + set up SSE when server data changes (navigation / invalidateAll)
  $effect(() => {
    const d = data;

    // Clear client overrides so merged values use fresh server data
    clientJob = null;
    clientSolutions = null;
    clientReportSummary = null;
    clientDiscoveryData = null;
    clientSolutionVotes = null;
    clientPreviewReport = null;

    clientSolutionVotesById = null;
    clientVoteRationales = null;
    // Reset UI state
    loading = false;
    error = "";
    discoveryLoading = false;
    gateApplyPending = false;
    summaryFetched = !!d.reportSummary;
    lastHandledStatus = d.job?.status ?? '';
    lastGateReachedAt = d.job?.gateReachedAt ?? null;
    solutionsLoading = false;
    solutionsFetchFailed = Boolean(d.solutionsFetchFailed);
    solutionsFetchAttempted =
      d.solutions !== null || Boolean(d.solutionsFetchFailed);
    regeneratingFromEmpty = false;
    regenerateFromEmptyError = "";
    // Fresh server data is the new draft-version baseline for the SSE drift guard.
    draftRefreshGuard.seedBaseline(d.job?.selectionDraft?.version);

    // Load the chat ledger regardless of whether SelectionWorkbench/ChatThread ever
    // mount this visit — its durable seed-evaluation receipts (chatLedger.hasPendingSeed)
    // feed the AWAITING_SELECTION mount guard below, which must know about a still-
    // evaluating (or just-settled) idea seed even on a reload where displaySolutions
    // and examinedRuledOut both happen to be empty.
    if (d.job?.id) void chatLedger.init(d.job.id);

    // Side effect: SSE subscription
    unsubscribeSSE?.();
    if (d.job && shouldKeepSSEOpen(d.job)) {
      connectSSE();
    }

    return () => { unsubscribeSSE?.(); };
  });

  // SSE transition handler: when job.status changes via SSE, fetch status-specific data
  $effect(() => {
    const currentJob = job;
    if (!currentJob || !jobId) return;
    const status = currentJob.status;
    const gateReachedAt = currentJob.gateReachedAt ?? null;
    const statusChanged = status !== lastHandledStatus;
    const gateReArrived = status === 'AWAITING_GATE' && gateReachedAt !== lastGateReachedAt;
    if (!statusChanged && !gateReArrived) return;
    lastHandledStatus = status;
    lastGateReachedAt = gateReachedAt;

    if (statusChanged && ['AWAITING_SELECTION', 'REGENERATING'].includes(status)) {
      if (!localSolutions || localSolutions.length === 0) {
        void fetchSolutions();
      }
      pollVotes(jobId);
      loadDiscoveryData(jobId);
      loadPreviewReport(jobId);
    }

    if (statusChanged && ['COMPLETED', 'FAILED', 'RUNNING_PHASE2'].includes(status)) {
      loadDiscoveryData(jobId);
      loadPreviewReport(jobId);
    }

    // apply_stay round-trip complete — the gate re-arrived (possibly at the same
    // gateStage, refreshed artifact). Drop the "keep GateWorkbench mounted" override.
    if (status === 'AWAITING_GATE' && gateApplyPending) {
      gateApplyPending = false;
    }

    // The chat ledger cache is stale on every checkpoint/selection/terminal arrival —
    // the server-created opening messages for the new stage aren't visible until we
    // force a reload. gateReArrived covers the same-gate apply_stay round-trip, where
    // status never actually changes.
    if (
      (statusChanged && (status === 'AWAITING_GATE' || status === 'AWAITING_SELECTION')) ||
      (
        statusChanged
        && Boolean(currentJob.awaitingSelectionAt)
        && ['QUEUED', 'RUNNING', 'REGENERATING'].includes(status)
      ) ||
      gateReArrived ||
      (statusChanged && ['COMPLETED', 'FAILED', 'CANCELLED'].includes(status))
    ) {
      void chatLedger.reload();
    }
  });

  function getStatusVariant(status: string): "success" | "warning" | "error" | "muted" | "info" | "accent" {
    switch (status) {
      case "COMPLETED": return "success";
      case "RUNNING": case "RUNNING_PHASE2": return "info";
      case "FAILED": return "error";
      case "CANCELLED": return "muted";
      case "AWAITING_SELECTION": return "accent";
      case "AWAITING_GATE": return "accent";
      case "REGENERATING": return "warning";
      default: return "warning";
    }
  }

  function getStatusLabel(status: string): string {
    switch (status) {
      case "AWAITING_SELECTION": return "Ready for Selection";
      case "AWAITING_GATE": return "Checkpoint reached";
      case "QUEUED": return "Queued";
      case "REGENERATING": return "Adding another batch";
      case "RUNNING_PHASE2": return "Deep Analysis";
      case "RUNNING": return "Running";
      case "COMPLETED": return "Completed";
      case "FAILED": return "Failed";
      case "CANCELLED": return "Cancelled";
      case "PENDING": return "Pending";
      default: return status;
    }
  }

  async function handleSelectionComplete() {
    connectSSE();
    invalidateAll();
  }

  function scrollToSolutions() {
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    document.getElementById('solution-selector')?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
  }

  function sentenceHeading(value: string | null | undefined): string {
    const trimmed = value?.trim();
    if (!trimmed) return 'Research';
    return trimmed.charAt(0).toUpperCase() + trimmed.slice(1);
  }

  const showSelectedSummary = $derived(
    (job?.selectedSolutions?.length ?? 0) > 0 &&
    (job?.solutionIdeas?.length ?? 0) > 0
  );


  const hasBatchActivity = $derived(
    chatLedger.jobId === jobId && chatLedger.batchActivities.length > 0,
  );

  // Admin-granted optional decision tools, resolved fresh per navigation by
  // (app)/+layout.server.ts. Fails closed if the layout fetch didn't land.
  const decisionTools = $derived(page.data.featureAccess?.decisionTools === true);

  // ── Unified dashboard state ──
  const isSelectionPhase = $derived(
    ['AWAITING_SELECTION', 'REGENERATING'].includes(job?.status ?? '') || isRegenQueued || seedRunning
  );
  const isTerminalStop = $derived(
    job?.status === 'FAILED' || job?.status === 'CANCELLED',
  );
  // A run that stops AFTER discovery still owns everything Phase 1 produced, and the owner
  // paid for it. Status alone cannot tell that apart from a run that died mid-discovery, so
  // key on the artifacts: the dossier only exists once Phase 1 got far enough to write it.
  const hasPhase1Work = $derived(Boolean(previewReport || discoveryData));
  const isStoppedWorkbench = $derived(isTerminalStop && hasPhase1Work);
  // Selection (G3) and guided-gate (G1/G2) phases share the same full-width,
  // aside-less hero/layout treatment — they're both "here's a checkpoint, review
  // it" screens rather than the running-research editorial hero.
  //
  // A stopped run that still completed discovery joins them: it is the same "here is
  // what exists, decide what to do with it" screen. The legacy run-overview shell
  // (phase-checklist nav + right-rail status panel + progress stepper) is for a run
  // still moving through the pipeline, which this one is not.
  const isWorkbenchPhase = $derived(
    isSelectionPhase || isGatePhase || isStoppedWorkbench,
  );

  // A job can arrive at AWAITING_SELECTION already zero-candidate on the initial
  // (SSR) load — the SSE status-transition effect above never fires for that case
  // since the status hasn't "changed" client-side. Auto-fetch once so the empty
  // state can tell "loading" apart from "fetch failed" apart from "genuinely zero"
  // instead of rendering nothing.
  $effect(() => {
    if (isSelectionPhase && displaySolutions.length === 0 && !solutionsLoading && !solutionsFetchAttempted) {
      void fetchSolutions();
    }
  });
  const isGeneratingP1 = $derived(
    ['RUNNING', 'QUEUED', 'PENDING'].includes(job?.status ?? '')
    && !isQueuedPhase2
    && !isRegenQueued
    && !isGatePhase
    && !seedRunning
  );
  const isGeneratingP2 = $derived(job?.status === 'RUNNING_PHASE2' || isQueuedPhase2);
  const isGenerating = $derived(isGeneratingP1 || isGeneratingP2);

  // Reset key: increments on major status transitions to clear user toggle state
  const sectionResetKey = $derived(
    isGeneratingP1 ? 'gen1'
    : isSelectionPhase ? 'selection'
    : isGeneratingP2 ? 'gen2'
    : job?.status === 'COMPLETED' ? 'complete'
    : 'other'
  );

  // Progress stepper step
  const stepperStep = $derived<'discovery' | 'selection' | 'deep_research'>(
    isGeneratingP1 ? 'discovery'
    : isSelectionPhase ? 'selection'
    : 'deep_research'
  );

  // Preview report derived values
  const nicheName = $derived(
    previewReport?.niche_context?.niche_input ??
    previewReport?.niche ??
    job?.niche ??
    ''
  );
  const pageTitle = $derived(
    isSelectionPhase
      ? sentenceHeading(nicheName)
      : isGatePhase
        ? (job?.gateStage === 1 ? 'Niche checkpoint' : 'Audience checkpoint')
        : titleCase(nicheName) || 'Research Progress',
  );

  const selectionSubtitle = 'Discovery is complete. Review the strongest opportunities before moving to Deep Research.';

  const gateSubtitle = $derived(
    job?.gateStage === 1
      ? `${sentenceHeading(nicheName)}. Review the niche framing before discovery search runs.`
      : `${sentenceHeading(nicheName)}. Review pain points and audience before ideation runs.`,
  );

  const dossier = $derived(createDiscoveryDisplayModel(previewReport, discoveryData));
  const discussionCount = $derived(dossier.discussionCount);
  const previewPainPointCount = $derived(dossier.painPointCount);
  const segmentCount = $derived(dossier.segmentCount);

  // Portfolio-funnel: findings examined but not carried forward (demoted winners, rejected
  // backfill candidates) + groups of surviving ideas that are variants of one product.
  const examinedRuledOut = $derived(previewReport?.examined_ruled_out ?? []);
  const overlapGroups = $derived(previewReport?.overlap_groups ?? []);
  const marketReality = $derived(previewReport?.market_reality ?? null);

  // A settled seed or batch changes several authoritative surfaces at once: candidates,
  // ruled-out evidence, status, limits, the active dispatch, and ledger-backed UI. Reload
  // the route contract as one snapshot instead of refreshing only two artifacts.
  function handleSeedSettled() {
    void invalidateAll();
  }

  // Placeholder data for locked sections - use short niche name, not full description
  const niche = $derived(previewReport?.niche ?? job?.niche ?? '');
  const placeholderNiche = $derived(stripLeadingArticle(nicheName || niche));
  const placeholderExec = $derived(placeholderExecutiveDashboard(placeholderNiche));
  const placeholderComp = $derived(placeholderCompetitors(placeholderNiche));

  // Real top pain point for preview hero (correct 0-1 scale)
  const topRealPain = $derived(
    dossier.painPoints[0] ?? null
  );

  // Preview hero: mix real Phase 1 data with fake Phase 2 data
  const previewHeroReport = $derived({
    ...placeholderExec,
    detailed_pain_points: previewReport?.detailed_pain_points ?? placeholderExec.detailed_pain_points,
    pain_point_analytics: previewReport?.pain_point_analytics ?? null,
    evidence_appendix: previewReport?.evidence_appendix ?? null,
    executive_dashboard: {
      ...placeholderExec.executive_dashboard,
      core_pain_point: topRealPain ? {
        title: topRealPain.title,
        severity_score: topRealPain.severity_score,
        commercial_intent_score: topRealPain.commercial_intent ?? (topRealPain as any).willingness_to_pay ?? 0,
      } : placeholderExec.executive_dashboard?.core_pain_point,
    },
  } as import('$lib/types/report').Report);

  const realFunnelStats = $derived({
    scanned: discoveryData?.methodology?.urls_searched ?? 0,
    relevant: discoveryData?.methodology?.urls_relevant ?? discussionCount,
    analyzed: (((previewReport?.research_metadata?.reddit_posts_analyzed ?? 0) + (previewReport?.research_metadata?.twitter_threads_analyzed ?? 0) + (previewReport?.research_metadata?.generic_posts_analyzed ?? 0)) || discussionCount),
    problems: previewPainPointCount,
    // Portfolio-funnel stages (concepts generated → candidates shown), when the backend
    // reports them. Optional/backward-compatible: undefined on reports without funnel_counts.
    funnelCounts: previewReport?.research_metadata?.funnel_counts ?? undefined,
  });

  // Sticky bar state removed - SelectionWorkbench owns its own fixed tray.

  // One stable severity order is shared with the public dossier.
  const topPainPoints = $derived(dossier.painPoints);
  const visiblePainPoints = $derived(
    isSelectionPhase ? topPainPoints.slice(0, 8) : topPainPoints
  );

  // Report-ready reveal: trigger once when job transitions to COMPLETED
  const isCompleted = $derived(job?.status === 'COMPLETED');
  // Dossier chrome (header + ledger + open-by-default) is about whether there IS a dossier
  // to read, not about whether the job is still live.
  const showDossierChrome = $derived(isSelectionPhase || isStoppedWorkbench);
  // Section open state driven by lifecycle (passes to ExpandableSection defaultOpen)
  const discoveryOpen = $derived(showDossierChrome);

  // Terminal-stop handoff copy. In the workbench shell there is no right rail, so this
  // card is the ONLY place the stop is explained — it carries both what happened and
  // what to do about it.
  const stopIsQuality = $derived(job?.stopReason === 'INSUFFICIENT_DATA');
  const deepResearchStageCost = $derived(
    (page.data.stageCosts as { deep_research?: number } | undefined)?.deep_research ?? 0,
  );
  const costsUnavailable = $derived(data.billingLoadState?.costsUnavailable === true);
  const catalogRetryLabel = $derived(
    costsUnavailable
      ? 'Retry Deep Research · price unavailable'
      : `Retry Deep Research · ${deepResearchStageCost} ${deepResearchStageCost === 1 ? 'credit' : 'credits'}`,
  );
  // The sidebar's single recovery row must name the same action as the card's primary
  // button; two different "next steps" on one screen is worse than none.
  const stopRecoverLabel = $derived(
    job?.status === 'CANCELLED'
      ? 'Start new research'
      : failedCatalogDeepResearch
        ? catalogRetryLabel
        : failedDuringDeepResearch
          ? 'Review selection'
          : 'Resume run',
  );
  const stopSubtitle = $derived(
    job?.status === 'CANCELLED'
      ? 'This run was cancelled. Everything discovery found is still here.'
      : failedCatalogDeepResearch
        ? 'Deep Research stopped before it finished. Retry the same catalog idea below.'
        : 'This run stopped after discovery. Everything it found is still here.',
  );
  const stopHandoffTitle = $derived(
    job?.status === 'CANCELLED'
      ? 'This research was cancelled'
      : failedCatalogDeepResearch
        ? 'Retry Deep Research for this idea'
        : stopIsQuality
          ? 'Not enough discussion data to continue'
          : failedDuringDeepResearch
            ? 'Review your saved shortlist'
            : hasPhase1Work
              ? 'The run stopped after discovery'
              : 'The run stopped before it finished',
  );
  const stopHandoffCopy = $derived(
    job?.status === 'CANCELLED'
      ? 'Nothing further will run on this job. Start a new run whenever you are ready.'
      : failedCatalogDeepResearch
        ? costsUnavailable
          ? "We couldn't load the current Deep Research price. Refresh this page before retrying; nothing will be charged."
          : `The retry uses the same catalog idea. Retrying Deep Research costs ${deepResearchStageCost} ${deepResearchStageCost === 1 ? 'credit' : 'credits'}; the charge happens when the retry is queued.`
        : stopIsQuality
          ? (job?.stopReasonDetails?.recommendation
              ?? 'Too few relevant discussions were found to produce a trustworthy result. A broader or differently-worded niche usually helps.')
          : failedDuringDeepResearch
            ? 'Return to selection and confirm Deep Research again. You will review the current price before any charge.'
            : job?.creditRefunded
              ? 'Resuming picks up from the last checkpoint and may re-charge the refunded stage at its original amount.'
              : 'Resuming picks up from the last checkpoint rather than re-running the whole pipeline.',
  );

  // Aside state for the editorial hero. Maps the live job status into one of
  // the JobHeroAside variants. Defaults to "running" while data is loading.
  const asideState = $derived<
    "running" | "queued" | "awaiting" | "regenerating" | "failed" | "cancelled"
  >(
    !job
      ? "running"
      : job.status === "FAILED"
          ? "failed"
          : job.status === "CANCELLED"
            ? "cancelled"
            : job.status === "AWAITING_SELECTION"
              ? "awaiting"
              : job.status === "REGENERATING" || isRegenQueued
                ? "regenerating"
                : job.status === "QUEUED" || job.status === "PENDING"
                  ? "queued"
                  : "running",
  );

  const reportAsset = $derived((job?.assets ?? []).find((a) => a.type === "REPORT_JSON"));
  const reportAvailable = $derived(Boolean(reportAsset));
  const landingAsset = $derived((job?.assets ?? []).find((a) => a.type === "LANDING_PAGE"));

  const lpStatus = $derived<'pending' | 'running' | 'completed' | 'failed' | 'locked'>(
    landingAsset ? 'completed'
    : job?.landingPageStatus === 'RUNNING' || job?.landingPageStatus === 'QUEUED' ? 'running'
    : job?.landingPageStatus === 'FAILED' ? 'failed'
    : job?.status === 'COMPLETED' && reportAsset ? 'pending'
    : 'locked'
  );

  // Advisory credit check for landing page
  const landingStageCost = $derived((page.data.stageCosts as any)?.landing_page ?? 5);
  const canAffordLanding = $derived((page.data.creditBalance as number ?? 0) >= landingStageCost);

  // Poll vote data while AWAITING_SELECTION
  $effect(() => {
    if (job?.status !== 'AWAITING_SELECTION' || !jobId) return;
    const id = jobId;
    let interval = setInterval(() => pollVotes(id), 30_000);
    function onVisibility() {
      if (document.hidden) {
        clearInterval(interval);
      } else {
        pollVotes(id);
        interval = setInterval(() => pollVotes(id), 30_000);
      }
    }
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  });

  // Fetch report summary when job transitions to completed via SSE
  $effect(() => {
    if (!isCompleted || !reportAsset) return;
    if (summaryFetched) return;
    summaryFetched = true;
    getReportSummary(job!.id)
      .then(s => { clientReportSummary = s; })
      .catch(() => { /* The completed handoff remains usable without the optional summary. */ });
  });


</script>

<svelte:head>
  <title>{job ? `${pageTitle || job.niche} - ${getStatusLabel(job.status)}` : 'Job'} - NicheIQ</title>
</svelte:head>

  <div class="job-page-shell">
  {#if job && !isGenerating}
    <PhaseNav
      jobStatus={job.status}
      entryMode={job.entryMode}
      mode={isSelectionPhase ? 'selection' : isGatePhase ? 'gate' : isStoppedWorkbench ? 'stopped' : 'default'}
      jobId={jobId ?? undefined}
      toolTasks={selectionToolTasks}
      selectedCount={sidebarSelectedCount}
      recoverLabel={isResuming
        ? (failedCatalogDeepResearch
            ? 'Retrying Deep Research...'
            : failedDuringDeepResearch
              ? 'Opening...'
              : 'Resuming...')
        : stopRecoverLabel}
      recoverOnclick={job.status === 'FAILED' ? resumeJob : undefined}
      recoverDisabled={isResuming || (failedCatalogDeepResearch && costsUnavailable)}
      availableSectionIds={showDossierChrome ? dossier.availableSectionIds : undefined}
      chatMode={job.chatMode ?? false}
      gateStage={job.gateStage ?? null}
      {decisionTools}
      landingPageStatus={lpStatus}
      {reportAvailable}
    />
  {/if}
  <!-- div, not <main>: the (app) layout already renders the page's single landmark <main>. -->
  <div
    class="job-page-content"
    class:job-page-content--selection={isWorkbenchPhase}
    class:job-page-content--completed={isCompleted}
  >
    <AnnotationProvider
      mode="owner"
      enabled={['AWAITING_SELECTION', 'REGENERATING'].includes(job?.status ?? '')}
      showLauncher={false}
      jobId={jobId ?? undefined}
    >
    {#if loading}
      <div class="text-center py-12">
        <Loader2 class="w-10 h-10 text-accent mx-auto animate-spin" />
        <p class="mt-4 text-text-secondary">Loading...</p>
      </div>
    {:else if error}
      <div class="card p-8 text-center">
        <div class="p-3 rounded-xl bg-error/10 border border-error/20 w-fit mx-auto">
          <AlertTriangle class="w-8 h-8 text-error" />
        </div>
        <h2 class="mt-4 text-xl font-semibold text-text-primary">Error</h2>
        <p class="mt-2 text-text-secondary">{error}</p>
        <Button onclick={() => goto("/new")} label="Start New Research" class="mt-6 btn-primary inline-block" />
      </div>
    {:else if job}
      {#if isGenerating}
        <!-- ═══ FOCUSED RESEARCH-IN-PROGRESS SCREEN (chrome hidden) ═══ -->
        <ResearchProgressScreen
          jobId={jobId ?? undefined}
          phase={isGeneratingP1 ? 'discovery' : 'deep_research'}
          jobStatus={job.status}
          niche={job.niche}
          entryMode={job.entryMode}
          userEmail={data.userEmail}
          progressPercent={job.progressPercent}
          stagesCompleted={job.stagesCompleted ?? 0}
          totalStages={job.totalStages ?? 0}
          currentStage={job.currentStage}
          currentStageName={job.currentStageName}
          queuePosition={job.queuePosition ?? undefined}
          catalogPainPoints={data.catalogPainPoints ?? []}
          selectedNames={job.selectedSolutions ?? []}
          selectedItems={job.selectionDraft?.items ?? []}
          solutionIdeas={job.solutionIdeas ?? []}
          primaryWinner={job.selectedSolution}
          onCancel={isGeneratingP1 ? cancelJob : undefined}
          {cancelling}
        />
      {:else}
      <!-- ═══ EDITORIAL HERO (1fr | 320px grid) ═══ -->
      <div
        class="job-hero-grid"
        class:job-hero-grid--selection={isWorkbenchPhase}
        class:job-hero-grid--completed={isCompleted}
      >
        <div class="job-hero-main" data-annotation-anchor="research-header">
          <PageHeader
            class={isWorkbenchPhase ? 'job-selection-header' : ''}
            icon={isWorkbenchPhase ? undefined : Telescope}
            breadcrumbItems={[{ label: 'Dashboard', href: '/dashboard' }]}
            breadcrumbCurrent={isSelectionPhase ? SHORTLIST_TITLE : isGatePhase ? 'Checkpoint' : isStoppedWorkbench ? 'Stopped run' : titleCase(nicheName) || 'Research'}
            title={pageTitle}
            titleVariant={isSelectionPhase || isStoppedWorkbench ? 'research-topic' : 'default'}
            subtitle={isSelectionPhase ? selectionSubtitle : isGatePhase ? gateSubtitle : isStoppedWorkbench ? stopSubtitle : undefined}
          >
            {#snippet metadata()}
              {#if job && nicheName !== job.niche}
                <p class="mt-1 text-sm text-text-muted truncate" title={job.niche}>
                  {job.niche.length > 100 ? job.niche.substring(0, 100) + '...' : job.niche}
                </p>
              {/if}
              {#if cancelError}
                <div class="mt-2 text-sm text-[color:var(--color-error-text)]">{cancelError}</div>
              {/if}
            {/snippet}
            {#snippet actions()}
              <div class="flex items-center gap-3 w-full sm:w-auto justify-end">
                {#if isSelectionPhase}
                  <TourRestartButton />
                {/if}
                {#if isSelectionPhase && displaySolutions.length > 0}
                  <button
                    bind:this={discoveryShareTrigger}
                    type="button"
                    onclick={() => (discoveryShareOpen = true)}
                    class="btn-ghost share-discovery-btn"
                    aria-label="Share discovery"
                    aria-haspopup="dialog"
                    aria-expanded={discoveryShareOpen}
                  >
                    <Share2 class="w-3.5 h-3.5" />
                    <span>Share</span>
                  </button>
                {/if}
                {#if !isWorkbenchPhase && !isCompleted}
                  <Badge variant={getStatusVariant(isRegenQueued ? 'REGENERATING' : job.status)}>
                    {#if ['RUNNING', 'RUNNING_PHASE2', 'REGENERATING'].includes(job.status) || isRegenQueued}
                      <Loader2 class="w-3.5 h-3.5 animate-spin" />
                    {/if}
                    {getStatusLabel(isRegenQueued ? 'REGENERATING' : job.status)}
                  </Badge>
                {/if}
              </div>
            {/snippet}
          </PageHeader>
          {#if isCompleted && reportAsset}
            <section class="completed-handoff" aria-labelledby="completed-handoff-title">
              <div>
                <p class="completed-handoff__eyebrow">Report ready</p>
                <div class="completed-handoff__title">
                  <h2 id="completed-handoff-title">Review the final recommendation</h2>
                  {#if completedVerdict}
                    <span class="completed-verdict {completedVerdict.tone}">
                      {completedVerdict.label}
                    </span>
                  {/if}
                </div>
                <p class="completed-handoff__copy">
                  See the recommendation, trace every conclusion to its evidence,
                  and turn the result into a practical plan.
                </p>
                {#if reportSummary?.primary_concern}
                  <p class="completed-handoff__concern">
                    <strong>Verify before acting:</strong> {reportSummary.primary_concern}
                  </p>
                {/if}
              </div>
              <Button
                href="/jobs/{job.id}/report"
                icon={REPORT_ICON}
                label="Open report"
                class="btn-primary"
              />
            </section>
          {:else if isCompleted}
            <section class="completed-handoff" aria-labelledby="completed-handoff-title" role="status">
              <div>
                <p class="completed-handoff__eyebrow">Report unavailable</p>
                <div class="completed-handoff__title">
                  <h2 id="completed-handoff-title">The report file has not arrived</h2>
                </div>
                <p class="completed-handoff__copy">
                  This run is marked complete, but there is no report to open yet. Refresh the
                  run before trying the report link again.
                </p>
              </div>
              <Button
                onclick={() => invalidateAll()}
                icon={RotateCw}
                label="Check again"
                class="btn-secondary"
              />
            </section>
          {/if}
        </div>
        {#if !isWorkbenchPhase && !isCompleted}
          <div class="job-hero-aside">
            <JobHeroAside
              state={asideState}
              progressPercent={job.progressPercent}
              stagesCompleted={jobStageCounts.completed}
              totalStages={jobStageCounts.total}
              startedAt={job.startedAt}
              selectionCount={displaySolutions.length}
              errorDetails={job.errorDetails}
              errorMessage={job.errorMessage}
              stopReason={job.stopReason}
              stopReasonDetails={job.stopReasonDetails}
              creditRefunded={job.creditRefunded}
            />
          </div>
        {/if}
      </div>

      {#if !isWorkbenchPhase && !isCompleted}
        <!-- ═══ PROGRESS STEPPER ═══ -->
        <ProgressStepper
          currentStep={stepperStep}
          {discussionCount}
          painPointCount={previewPainPointCount}
          solutionCount={displaySolutions.length}
        />
      {/if}

      <!-- ═══ TERMINAL-STOP HANDOFF ═══
           One card, same recipe as .completed-handoff: what happened is already stated by
           JobHeroAside in the right rail, so this carries the NEXT STEP only. The previous
           three stacked banners restated the aside's headline, guidance and refund line
           verbatim in hand-rolled Tailwind. -->
      {#if isTerminalStop}
        <section id="recover-run" class="stop-handoff" aria-labelledby="stop-handoff-title">
          <div>
            <p class="stop-handoff__eyebrow" class:is-cancelled={job.status === 'CANCELLED'}>
              {job.status === 'CANCELLED' ? 'Cancelled' : stopIsQuality ? 'Stopped early' : 'Run failed'}
            </p>
            <div class="stop-handoff__title">
              <h2 id="stop-handoff-title">{stopHandoffTitle}</h2>
              {#if job.creditRefunded}
                <span class="stop-refund">Credits refunded</span>
              {/if}
            </div>
            <p id="stop-handoff-copy" class="stop-handoff__copy">{stopHandoffCopy}</p>
            {#if hasPhase1Work}
              <p class="stop-handoff__retained">
                <strong>Your discovery work is intact.</strong>
                The evidence below — and the {displaySolutions.length}
                {displaySolutions.length === 1 ? 'idea' : 'ideas'} it produced — came from the
                completed part of this run and is unaffected.
              </p>
            {/if}
            {#if resumeError}
              <p class="stop-handoff__error">{resumeError}</p>
            {/if}
          </div>
          <div class="stop-handoff__actions">
            {#if job.status === 'FAILED'}
              <SubmitButton
                onclick={resumeJob}
                loading={isResuming}
                loadingText={failedCatalogDeepResearch
                  ? "Retrying Deep Research..."
                  : failedDuringDeepResearch
                    ? "Opening..."
                    : "Resuming..."}
                icon={RotateCw}
                keepIconOnLoad
                disabled={failedCatalogDeepResearch && costsUnavailable}
                describedBy="stop-handoff-copy"
                title={failedCatalogDeepResearch && costsUnavailable
                  ? "Current Deep Research price unavailable. Refresh to try again."
                  : undefined}
                label={failedCatalogDeepResearch
                  ? catalogRetryLabel
                  : failedDuringDeepResearch
                    ? "Review selection"
                    : "Resume from checkpoint"}
                class="btn-primary"
              />
            {/if}
            <Button
              href={`/new?fromJob=${job.id}&prefilled=${encodeURIComponent(job.niche)}`}
              label="Start new research"
              class={job.status === 'FAILED' ? 'btn-secondary' : 'btn-primary'}
            />
          </div>
        </section>
      {/if}

      <!-- ═══ DASHBOARD SECTIONS ═══ -->
      {#if !isGeneratingP1}
        {#if isSelectionPhase && invalidSolutionCount > 0}
          <div class="candidate-data-warning" role="alert">
            <div>
              <strong>
                {invalidSolutionCount} malformed {invalidSolutionCount === 1 ? "candidate was" : "candidates were"} hidden
              </strong>
              <p>The valid ideas remain available. Retry to check for a repaired shortlist.</p>
            </div>
            <SubmitButton
              onclick={fetchSolutions}
              loading={solutionsLoading}
              loadingText="Retrying..."
              icon={RotateCw}
              keepIconOnLoad
              label="Retry candidates"
              class="btn-secondary"
            />
          </div>
        {/if}

        {#if isSelectionPhase && (
          displaySolutions.length > 0
          || examinedRuledOut.length > 0
          || seedPending
          || hasBatchActivity
        )}
          <SelectionWorkbench
            jobId={jobId ?? ''}
            solutions={displaySolutions}
            selectionDraft={job.selectionDraft ?? null}
            coverageNotes={previewReport?.data_quality_summary?.quality_caveats ?? []}
            {examinedRuledOut}
            {overlapGroups}
            {marketReality}
            ideaPortfolioSummary={previewReport?.idea_portfolio_summary ?? null}
            userAdjustments={previewReport?.user_adjustments ?? []}
            {discussionCount}
            painPointCount={previewPainPointCount}
            {segmentCount}
            creditBalance={page.data.creditBalance ?? 0}
            stageCosts={page.data.stageCosts ?? { discovery: 5, deep_research: 15, landing_page: 5, regenerate_ideas: 2 }}
            canRegenerate={job.canRegenerate ?? false}
            ideaBatchCompletedCount={job.ideaBatchCompletedCount ?? null}
            maxIdeaBatches={job.maxIdeaBatches ?? null}
            isRegenerating={job.status === 'REGENERATING' || isRegenQueued}
            poolMutationLocked={seedRunning}
            selectedSolutions={job.selectedSolutions ?? undefined}
            selectedSolutionIds={job.selectedSolutionIds ?? undefined}
            decisionProfile={job.selectionDecisionProfile ?? null}
            {solutionVotes}
            onComplete={handleSelectionComplete}
            onRegenerateStart={() => {
              clientJob = { ...job!, status: 'QUEUED', activeDispatchKind: 'REGENERATE' };
              void invalidateAll();
            }}
            onBatchSettled={handleSeedSettled}
            onJourneyTasks={(tasks) => selectionToolTasks = tasks}
            onShortlistChange={(count) => liveShortlist = { jobId: jobId ?? '', count }}
            onShortlistVersionChange={(version) => draftRefreshGuard.reportLocalVersion(version)}
            onSeedSettled={handleSeedSettled}
            {solutionVotesById}
            {voteRationales}
            {decisionTools}
          />
        {:else if isSelectionPhase}
          <!-- ═══ ZERO-CANDIDATE STATES ═══ Selection reached but nothing to show:
               loading (still fetching), fetch failed (real error, retry), or a
               genuinely empty result (offer to regenerate / start over). ── -->
          <div class="card p-8 text-center mb-6">
            {#if solutionsLoading}
              <Loader2 class="w-8 h-8 text-accent mx-auto animate-spin" />
              <p class="mt-4 text-text-secondary">Loading candidates&hellip;</p>
            {:else if solutionsFetchFailed}
              <div class="err-icon-box p-3 rounded-xl w-fit mx-auto">
                <AlertTriangle class="w-8 h-8" />
              </div>
              <h2 class="mt-4 text-xl font-semibold text-text-primary">Couldn't load candidates</h2>
              <p class="mt-2 text-text-secondary">Something went wrong fetching the shortlist for this run.</p>
              <SubmitButton
                onclick={fetchSolutions}
                loading={solutionsLoading}
                loadingText="Retrying..."
                icon={RotateCw}
                keepIconOnLoad
                label="Retry"
                class="btn-primary mt-6 inline-flex items-center gap-2"
              />
            {:else}
              <div class="p-3 rounded-xl bg-text-muted/10 w-fit mx-auto">
                <Package class="w-8 h-8 text-text-muted" />
              </div>
              <h2 class="mt-4 text-xl font-semibold text-text-primary">No candidates yet</h2>
              <p class="mt-2 text-text-secondary">Discovery didn't produce a shortlist for this run.</p>
              {#if job.canRegenerate}
                <SubmitButton
                  onclick={regenerateFromEmpty}
                  disabled={costsUnavailable}
                  loading={regeneratingFromEmpty}
                  loadingText="Adding batch..."
                  label={costsUnavailable
                    ? "Add idea batch · price unavailable"
                    : `Add idea batch · ${regenerateFromEmptyCost} ${regenerateFromEmptyCost === 1 ? "credit" : "credits"}`}
                  class="btn-primary mt-6 inline-block"
                />
                {#if costsUnavailable}
                  <p class="mt-3 text-sm text-text-secondary">
                    Current pricing could not be loaded. Reload before adding a paid batch.
                  </p>
                {/if}
                {#if regenerateFromEmptyError}
                  <p class="mt-3 text-sm text-[color:var(--color-error-text)]">{regenerateFromEmptyError}</p>
                {/if}
              {:else}
                {#if (
                  typeof job.ideaBatchCompletedCount === "number"
                  && typeof job.maxIdeaBatches === "number"
                  && job.maxIdeaBatches > 0
                )}
                  <p class="mt-4 font-mono text-xs text-text-secondary">
                    {job.ideaBatchCompletedCount} of {job.maxIdeaBatches} additional batches used
                  </p>
                  <SubmitButton
                    disabled
                    loadingText="Adding batch..."
                    label="Add idea batch · limit reached"
                    class="btn-primary mt-6 inline-block"
                  />
                {/if}
                <button onclick={() => goto(`/new?fromJob=${job.id}&prefilled=${encodeURIComponent(job.niche)}`)} class="mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-accent-dark hover:text-accent-hover transition-colors">
                  Start new research <ArrowRight class="w-4 h-4" />
                </button>
              {/if}
            {/if}
          </div>
        {/if}

        {#if isGatePhase && (job.gateStage === 1 || job.gateStage === 4)}
          <GateWorkbench
            jobId={jobId ?? ''}
            gateStage={job.gateStage}
            gateArtifact={job.gateArtifact ?? null}
            gateApplyCount={job.gateApplyCount ?? 0}
            gateReachedAt={job.gateReachedAt ?? null}
            jobStatus={job.status}
            guidedCosts={page.data.stageCosts?.guided ?? null}
            onContinueStart={() => {
              // Continue ALWAYS clears a lingering apply_stay override: if the SSE stream
              // died during a long gate dwell, the apply's re-arrival was never observed and
              // gateApplyPending stayed true — without this clear, the optimistic QUEUED
              // below keeps the workbench mounted (disabled "Sending to worker…") instead of
              // handing off to the progress screen (live-caught 2026-07-12).
              gateApplyPending = false;
              clientJob = { ...job!, status: 'QUEUED' };
              connectSSE(); // revive a possibly-dead stream exactly when updates matter
            }}
            onApplyStayStart={() => { gateApplyPending = true; connectSSE(); }}
            onApplyStayError={() => { gateApplyPending = false; }}
          />
        {/if}

        {#if !isCompleted && (previewReport || discoveryData || discoveryFetchFailed || previewFetchFailed)}
          <div class="discovery-sections" class:discovery-dossier={showDossierChrome} data-annotation-anchor="research-dossier">
            {#if discoveryFetchFailed || previewFetchFailed}
              <div class="dossier-load-warning" role="alert">
                <div>
                  <strong>Part of the Discovery dossier could not be loaded</strong>
                  <p>Available findings are shown below. Retry to restore the missing context.</p>
                </div>
                <SubmitButton
                  onclick={retryDiscoveryDossier}
                  loading={discoveryLoading || previewReportLoading}
                  loadingText="Retrying..."
                  icon={RotateCw}
                  keepIconOnLoad
                  label="Retry dossier"
                  class="btn-secondary"
                />
              </div>
            {/if}
            {#if showDossierChrome}
              <div class="dossier-header">
                <div>
                  <p class="dossier-eyebrow">Discovery dossier</p>
                  <h2 class="dossier-title">
                    {isSelectionPhase ? 'Evidence behind the shortlist' : 'What discovery found'}
                  </h2>
                  <p class="dossier-copy">Market context, demand signals, pain clusters, and source quality from the discovery run.</p>
                </div>
                <dl class="dossier-ledger" aria-label="Discovery evidence summary">
                  <div>
                    <dt>Discussions</dt>
                    <dd>{discussionCount.toLocaleString()}</dd>
                  </div>
                  <div>
                    <dt>Pain points</dt>
                    <dd>{previewPainPointCount}</dd>
                  </div>
                  <div>
                    <dt>Communities</dt>
                    <dd>{dossier.communityNames.length}</dd>
                  </div>
                </dl>
              </div>
            {/if}

            <!-- Overview -->
            {#if previewReport}
              <ExpandableSection
                title="Overview"
                variant="default"
                defaultOpen={!isSelectionPhase}
                resetKey={sectionResetKey}
                id="overview"
              >
                <PreviewOverview
                  nicheDescription={previewReport.niche_context?.niche_description}
                  {discussionCount}
                  painPointCount={previewPainPointCount}
                  solutionCount={displaySolutions.length}
                  {segmentCount}
                  showFacts={!isSelectionPhase}
                />
                {#if previewReport.niche_difficulty_verdict}
                  <NicheRealityCheck verdict={previewReport.niche_difficulty_verdict} context="discovery" />
                {/if}
              </ExpandableSection>
            {/if}

            <!-- Opportunities (post-selection summary) -->
            {#if !isSelectionPhase && displaySolutions.length > 0}
              <ExpandableSection
                title="Opportunities"
                count={displaySolutions.length}
                countSuffix="opportunities"
                variant="accent"
                defaultOpen={false}
                resetKey={sectionResetKey}
                id="opportunities"
              >
                {#if showSelectedSummary && !isGeneratingP2}
                  <SelectedSolutionsSummary
                    selectedNames={job.selectedSolutions ?? []}
                    selectedItems={job.selectionDraft?.items ?? []}
                    solutionIdeas={job.solutionIdeas ?? []}
                    primaryWinner={job.selectedSolution}
                    status={job.status}
                    jobId={jobId ?? undefined}
                  />
                {/if}
              </ExpandableSection>
            {/if}

            <!-- Market Snapshot -->
            {#if discoveryData?.discussion_trend?.length}
              <ExpandableSection
                title="Market Snapshot"
                icon={BarChart3}
                defaultOpen={!isSelectionPhase}
                resetKey={sectionResetKey}
                id="market-snapshot"
              >
                <MarketSnapshot
                  discussionsAnalyzed={discussionCount}
                  communityCount={dossier.communityNames.length}
                  totalEngagement={dossier.totalEngagement}
                  trend={discoveryData.discussion_trend}
                  growthPct={discoveryData.discussion_growth_pct ?? null}
                />
              </ExpandableSection>
            {/if}

            <!-- Pain Points -->
            {#if previewReport?.detailed_pain_points?.length}
              <ExpandableSection
                title="Pain Points"
                count={previewPainPointCount}
                countSuffix="clusters"
                variant={isSelectionPhase ? "default" : "success"}
                defaultOpen={!isSelectionPhase && discoveryOpen}
                resetKey={sectionResetKey}
                id="pain-points"
              >
                <p class="section-intro">Pain clusters from discovery, ordered by reported severity.</p>
                {#each visiblePainPoints as pp, i}
                  <PainPointSummaryCard painPoint={pp} rank={i + 1} isTop={i === 0} onViewOpportunity={scrollToSolutions} />
                {/each}
                {#if isSelectionPhase && topPainPoints.length > visiblePainPoints.length}
                  <p class="section-footnote">
                    Showing the {visiblePainPoints.length} highest-signal clusters for selection. {topPainPoints.length - visiblePainPoints.length} lower-priority clusters stay in the discovery record.
                  </p>
                {/if}

              </ExpandableSection>
            {/if}

            <!-- Audience -->
            {#if previewReport?.audience_mapping}
              {#if isSelectionPhase}
                <ExpandableSection
                  title="Audience"
                  count={segmentCount}
                  countSuffix="segments"
                  variant="default"
                  defaultOpen={false}
                  resetKey={sectionResetKey}
                  id="audience"
                >
                    <AudienceSnapshot data={previewReport.audience_mapping} />
                </ExpandableSection>
              {:else}
                <AudienceSection data={previewReport.audience_mapping} />
              {/if}
            {/if}

            <!-- Community & Sources -->
            {#if discoveryData || previewReport?.evidence_appendix}
              <ExpandableSection
                title="Community & Sources"
                count={dossier.communityNames.length}
                countSuffix="communities"
                variant={isSelectionPhase ? "default" : "success"}
                defaultOpen={false}
                resetKey={sectionResetKey}
                id="community"
              >
                <CommunitySourcesSection
                  subredditNames={discoveryData?.subreddit_names}
                  communityHubs={previewReport?.audience_mapping?.community_hubs}
                  postsAnalyzed={discussionCount || undefined}
                  sourcesSearched={discoveryData?.sources_searched}
                />

                {#if discoveryData?.methodology}
                  <p class="methodology-note">
                    Based on {discoveryData.methodology.urls_searched.toLocaleString()} URLs scanned &middot;
                    {discoveryData.methodology.urls_relevant} relevant ({discoveryData.methodology.filtering_rate}%) &middot;
                    {discoveryData.methodology.quality_tier} quality
                  </p>
                {/if}

                {#if discoveryData?.social_posts_sample?.length}
                  <DiscoveryEvidence data={discoveryData} />
                {/if}
              </ExpandableSection>
            {/if}
          </div>
        {/if}

        <!-- ═══ DEEP RESEARCH PREVIEW SECTIONS ═══ -->
        <!-- Suppressed at guided-gate checkpoints: mid-Phase-1 there is no real data
             behind the funnel/SEO/competitor previews, and the checkpoint ledger is
             the page's single job. -->
        {#if !isCompleted && !isSelectionPhase && !isGatePhase}
          <!-- Capped preview: UnifiedHero with real blurred content -->
          <div class="preview-capped">
            <div aria-hidden="true" inert>
              <UnifiedHero
                report={previewHeroReport}
                nicheName={nicheName}
                nicheDescription={previewReport?.niche_context?.niche_description ?? `Analysis of the ${niche} market`}
                funnelStats={realFunnelStats}
                previewMode={true}
              />
            </div>
            <div class="preview-capped-fade"></div>
            <div class="preview-capped-label">
              <span class="preview-capped-badge">Unlocks with Deep Research</span>
            </div>
          </div>

          <!-- SEO Keywords preview - editorial hairline insert between capped cards -->
          <div aria-hidden="true" inert>
            <SEOKeywordsPreview nicheName={placeholderNiche} />
          </div>
          <p class="sr-only">SEO keyword strategy unlocks with Deep Research.</p>

          <!-- Capped preview: Competitors with real blurred content -->
          <div class="preview-capped preview-capped--sm">
            <div aria-hidden="true" inert>
              <Competitors
                profiles={placeholderComp.profiles}
                analysis={placeholderComp.analysis}
                analytics={placeholderComp.analytics}
                selectedSolutionName={`${placeholderNiche} Opportunity Analyzer`}
                previewMode={true}
              />
            </div>
            <div class="preview-capped-fade"></div>
            <div class="preview-capped-label">
              <span class="preview-capped-badge">Unlocks with Deep Research</span>
            </div>
          </div>
        {/if}

        <!-- ═══ OPTIONAL DELIVERABLES ═══ -->
        {#if isCompleted}
          <section class="extras-card" id="optional-deliverables" aria-labelledby="optional-deliverables-title">
            <div class="extras-header">
              <div class="extras-header-left">
                <div class="extras-icon-box"><Package class="extras-icon" /></div>
                <div class="extras-title-group">
                  <h2 class="extras-title" id="optional-deliverables-title">Optional deliverables</h2>
                  <span class="extras-subtitle">Create only what you need next</span>
                </div>
              </div>
              {#if lpStatus === 'completed'}
                <span class="extras-ready-badge"><CheckCircle class="extras-ready-icon" /> Ready</span>
              {/if}
            </div>
            <div class="extras-divider"></div>
            <div class="extras-content">
              <DeliverableRow
                label="Landing Page"
                icon={STAGE_MAP.landing_page.icon}
                status={lpStatus}
                creditCost={landingStageCost}
                canAfford={canAffordLanding}
                priceAvailable={!costsUnavailable}
                asset={landingAsset}
                generating={generatingLanding}
                error={landingError}
                onGenerate={generateLanding}
              />
            </div>
          </section>
        {/if}
      {/if}

      <!-- ═══ RUN PROVENANCE ═══ -->
      <div class="mt-6 p-4 rounded-lg bg-bg-surface border border-border">
        <div class="run-meta">
          <span class="run-meta__timeline">
            <span class="run-meta__dot" class:run-meta__dot--done={job.completedAt}></span>
            <span>{runTimeline}</span>
          </span>
          <button
            type="button"
            class="run-meta__id"
            onclick={copyRunId}
            aria-label={`Run ID ${job.id.slice(0, 8)}. Copy full run ID`}
          >
            <span class="run-meta__id-label">Run ID</span>
            <code>{job.id.slice(0, 8)}</code>
            {#if copiedRunId}
              <CheckCircle class="run-meta__id-icon run-meta__id-icon--done" />
            {:else}
              <Copy class="run-meta__id-icon" />
            {/if}
          </button>
          <span class="sr-only" role="status" aria-live="polite">{copiedRunId ? "Run ID copied to clipboard" : ""}</span>
        </div>
      </div>
      {/if}
    {/if}
    </AnnotationProvider>
  </div>
</div>

{#if jobId}
  <ShareDiscoveryModal
    bind:open={discoveryShareOpen}
    jobId={jobId}
    restoreFocusTo={discoveryShareTrigger}
  />
{/if}

<!-- First-run tutorial. `selectionToolTasks !== undefined` is the signal that the
     CLIENT-side decision-state fetch landed: until it does, the shortlist dock has not
     mounted and the guide card still reads "Updating your next useful step…", so two of
     the five steps would have nothing to point at. -->
{#if isSelectionPhase}
  <TourHost
    chapter="job-shortlist"
    enabled={decisionTools}
    ready={displaySolutions.length > 0
      && !solutionsLoading
      && selectionToolTasks !== undefined}
    deferred={seedRunning || isRegenQueued || invalidSolutionCount > 0}
    reflowKey={selectionToolTasks}
  />
{/if}

<style>
  /* Error-state icon box (zero-candidate fetch failure) — status tokens
     instead of Tailwind opacity slicing on the raw `error` color. */
  .err-icon-box {
    background: color-mix(in srgb, var(--color-error-text) 10%, transparent);
    border: 1px solid color-mix(in srgb, var(--color-error-text) 25%, transparent);
    color: var(--color-error-text);
  }

  /* Run provenance strip — reads as intentional metadata, not debug output. */
  .run-meta {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--space-2) var(--space-4);
  }
  .run-meta__timeline {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-sm);
    line-height: var(--leading-normal);
    color: var(--color-text-secondary);
  }
  .run-meta__dot {
    flex-shrink: 0;
    width: var(--space-1-5);
    height: var(--space-1-5);
    border-radius: var(--radius-full);
    background: color-mix(in srgb, var(--color-text-muted) 55%, transparent);
  }
  .run-meta__dot--done {
    background: var(--color-success);
  }
  .run-meta__id {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1-5);
    min-height: var(--space-8);
    padding: var(--space-1) var(--space-2);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-bg-elevated);
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    cursor: pointer;
    transition:
      border-color var(--duration-fast) var(--ease-default),
      color var(--duration-fast) var(--ease-default);
  }
  .run-meta__id:hover {
    border-color: var(--color-border-emphasis);
    color: var(--color-text-primary);
  }
  .run-meta__id:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .run-meta__id-label {
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: var(--tracking-label);
    text-transform: uppercase;
  }
  .run-meta__id code {
    font-family: var(--font-mono);
    letter-spacing: 0.01em;
  }
  .run-meta__id :global(.run-meta__id-icon) {
    width: var(--space-3);
    height: var(--space-3);
    color: var(--color-text-muted);
  }
  .run-meta__id :global(.run-meta__id-icon--done) {
    color: var(--color-success-text);
  }

  /* Share discovery button (header actions) — uses the global .btn-ghost
     recipe (components.css); this only adds the states it doesn't define. */
  .share-discovery-btn:active {
    transform: scale(0.98);
  }
  .share-discovery-btn:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  /* ═══ Page shell: sidebar + content ═══ */
  .job-page-shell {
    display: flex;
    min-height: calc(100dvh - 3.5rem);
  }

  /* Below the desktop-sidebar breakpoint the sidebar is hidden; stack the shell
     so the in-flow selection mobile nav becomes a full-width top bar instead of
     being stretched into a full-height flex column. */
  @media (max-width: 1279px) {
    .job-page-shell {
      flex-direction: column;
    }
  }

  .job-page-content {
    width: min(56rem, 100%);
    margin: 0 auto;
    min-width: 0;
    padding: 2rem 2.5rem 5rem;
  }

  .job-page-content--selection {
    width: min(76rem, 100%);
  }

  .job-page-content--completed {
    width: min(76rem, 100%);
  }

  /* .discovery-sections / .discovery-dossier / .dossier-* / dossier section-chrome
     styles moved to src/lib/styles/discovery-dossier.css
     (global; shared with SharedDiscoveryView). */

  :global(.job-selection-header) {
    margin-bottom: 0;
  }

  .candidate-data-warning,
  .dossier-load-warning {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-4);
    margin-bottom: var(--space-4);
    padding: var(--space-4);
    border: 1px solid color-mix(in srgb, var(--color-warning) 28%, var(--color-border));
    border-radius: var(--radius-md);
    background: var(--color-warning-subtle);
    color: var(--color-text-primary);
  }

  .candidate-data-warning strong,
  .dossier-load-warning strong {
    font-size: var(--text-sm);
    font-weight: 700;
  }

  .candidate-data-warning p,
  .dossier-load-warning p {
    margin: var(--space-1) 0 0;
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    line-height: var(--leading-normal);
  }

  :global(.job-selection-header .page-header-body) {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: start;
    gap: var(--space-3);
  }

  :global(.job-selection-header .page-header-title-row) {
    min-width: 0;
    gap: var(--space-3);
  }

  :global(.job-selection-header .page-header-actions) {
    justify-self: end;
    padding-top: 0;
  }

  :global(.job-selection-header .page-header-title-row > div:first-child) {
    padding: var(--space-2);
    border-radius: var(--radius-md);
  }

  :global(.job-selection-header .page-header-title-row svg) {
    width: 1.25rem;
    height: 1.25rem;
  }

  @media (max-width: 639px) {
    :global(.job-selection-header .page-header-body) {
      grid-template-columns: minmax(0, 1fr);
    }

    :global(.job-selection-header .page-header-actions) {
      justify-self: start;
    }
  }

  @media (max-width: 1279px) {
    .job-page-content {
      padding: 1rem;
      width: 100%;
    }
  }

  /* ═══ Editorial hero (1fr | 320px) ═══
     Hero is constrained to .job-page-content's width (56rem). The flex
     page-shell makes a viewport-based break-out unsafe (it would push the
     title behind the PhaseNav sidebar on wide viewports), so we keep the
     grid in-flow. Aside is sticky alongside the body below it. */
  .job-hero-grid {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 300px;
    gap: 1.5rem;
    margin-bottom: 1.5rem;
  }
  .job-hero-grid--selection {
    grid-template-columns: minmax(0, 1fr);
    align-items: start;
    gap: 0;
    margin-bottom: 0;
  }
  .job-hero-grid--completed {
    grid-template-columns: minmax(0, 1fr);
    gap: 0;
    margin-bottom: var(--space-8);
  }
  .job-hero-main {
    min-width: 0;
  }
  .job-hero-aside {
    position: sticky;
    top: 5rem;
    align-self: start;
  }
  @media (max-width: 1023px) {
    .job-hero-grid {
      grid-template-columns: 1fr;
    }
    .job-hero-aside {
      position: static;
    }
  }

  .completed-handoff {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-6);
    margin-top: var(--space-6);
    padding: var(--space-6);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-bg-elevated);
  }

  .completed-handoff > div {
    min-width: 0;
  }

  .completed-handoff__eyebrow {
    margin: 0 0 var(--space-2);
    color: var(--color-success-text);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .completed-handoff__title {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-3);
    align-items: center;
  }

  .completed-handoff h2 {
    margin: 0;
    color: var(--color-text-primary);
    font-family: var(--font-display);
    font-size: var(--text-xl);
    font-weight: 700;
    line-height: var(--leading-tight);
  }

  .completed-verdict {
    display: inline-flex;
    align-items: center;
    min-height: var(--space-6);
    padding-inline: var(--space-3);
    border-radius: var(--radius-full);
    font-size: var(--text-xs);
    font-weight: 700;
  }

  .completed-verdict.positive {
    color: var(--color-success-text);
    background: var(--color-success-subtle);
  }

  .completed-verdict.caution {
    color: var(--color-warning-text);
    background: var(--color-warning-subtle);
  }

  .completed-verdict.negative {
    color: var(--color-error-text);
    background: var(--color-error-subtle);
  }

  .completed-handoff__copy {
    max-width: 58ch;
    margin: var(--space-2) 0 0;
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: var(--leading-relaxed);
  }

  .completed-handoff__concern {
    max-width: 68ch;
    margin: var(--space-3) 0 0;
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: var(--leading-relaxed);
  }

  .completed-handoff__concern strong {
    color: var(--color-warning-text);
  }

  :global(.completed-handoff .btn-primary) {
    flex-shrink: 0;
  }

  @media (max-width: 639px) {
    .completed-handoff {
      align-items: stretch;
      flex-direction: column;
    }

    :global(.completed-handoff .btn-primary) {
      justify-content: center;
      width: 100%;
    }
  }

  /* ═══ Terminal-stop handoff (FAILED / CANCELLED) ═══
     Deliberately the same shell as .completed-handoff — a run that ended is a run that
     ended, and the only difference between them is which action comes next. */
  .stop-handoff {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-6);
    margin-bottom: var(--space-6);
    padding: var(--space-6);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-bg-elevated);
  }

  .stop-handoff > div {
    min-width: 0;
  }

  .stop-handoff__eyebrow {
    margin: 0 0 var(--space-2);
    color: var(--color-error-text);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  /* A cancellation is a user's own decision, not a fault — muted, never error red. */
  .stop-handoff__eyebrow.is-cancelled {
    color: var(--color-text-muted);
  }

  .stop-handoff__title {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-3);
    align-items: center;
  }

  .stop-handoff h2 {
    margin: 0;
    color: var(--color-text-primary);
    font-family: var(--font-display);
    font-size: var(--text-xl);
    font-weight: 700;
    line-height: var(--leading-tight);
  }

  .stop-refund {
    display: inline-flex;
    align-items: center;
    min-height: var(--space-6);
    padding-inline: var(--space-3);
    border-radius: var(--radius-full);
    font-size: var(--text-xs);
    font-weight: 700;
    color: var(--color-success-text);
    background: var(--color-success-subtle);
  }

  .stop-handoff__copy {
    max-width: 58ch;
    margin: var(--space-2) 0 0;
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: var(--leading-relaxed);
  }

  .stop-handoff__retained {
    max-width: 68ch;
    margin: var(--space-3) 0 0;
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: var(--leading-relaxed);
  }

  .stop-handoff__retained strong {
    color: var(--color-text-primary);
  }

  .stop-handoff__error {
    margin: var(--space-3) 0 0;
    color: var(--color-error-text);
    font-size: var(--text-sm);
  }

  .stop-handoff__actions {
    display: flex;
    flex-shrink: 0;
    flex-wrap: wrap;
    gap: var(--space-3);
  }

  @media (max-width: 639px) {
    .stop-handoff {
      align-items: stretch;
      flex-direction: column;
    }

    .stop-handoff__actions {
      flex-direction: column;
    }

    :global(.stop-handoff__actions .btn-primary),
    :global(.stop-handoff__actions .btn-secondary) {
      justify-content: center;
      width: 100%;
    }
  }

  /* ═══ Section intro ═══ */
  .section-intro {
    max-width: 74ch;
    font-size: var(--text-13);
    color: var(--color-text-secondary);
    line-height: var(--leading-relaxed);
    margin: 0 0 var(--space-3);
    text-wrap: pretty;
  }

  .section-footnote {
    margin: var(--space-3) 0 0;
    padding-top: var(--space-3);
    border-top: 1px solid color-mix(in srgb, var(--color-border) 72%, transparent);
    color: var(--color-text-muted);
    font-size: var(--text-sm);
    line-height: var(--leading-normal);
    text-wrap: pretty;
  }

  /* ═══ Methodology footnote ═══ */
  .methodology-note {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--color-text-muted);
    line-height: var(--leading-normal);
    letter-spacing: var(--tracking-normal);
    margin: var(--space-3) 0 0;
    padding-top: var(--space-3);
    border-top: 1px solid var(--color-border);
  }

  /* .preview-capped* classes moved to src/lib/styles/preview-capped.css
     (global; shared with SharedDiscoveryView). */

  /* ── Optional deliverables ── */
  .extras-card {
    margin-top: var(--space-4);
    padding: 0;
    border-radius: var(--radius-lg);
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    overflow: hidden;
  }

  /* extras-card--locked removed - extras only shown when complete */

  .extras-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-3) var(--space-4);
  }

  .extras-header-left {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }

  .extras-icon-box {
    width: var(--space-8);
    height: var(--space-8);
    border-radius: var(--radius-md);
    background: var(--color-accent-subtle);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  :global(.extras-icon) {
    width: var(--space-4);
    height: var(--space-4);
    color: var(--color-accent);
  }

  .extras-title-group {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .extras-title {
    margin: 0;
    font-size: var(--text-base);
    font-weight: 700;
    color: var(--color-text-primary);
    line-height: var(--leading-tight);
  }

  .extras-subtitle {
    font-size: var(--text-sm);
    color: var(--color-text-muted);
    line-height: var(--leading-normal);
  }

  .extras-ready-badge {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    font-size: var(--text-xs);
    font-weight: 600;
    color: var(--color-success-text);
    background: var(--color-success-subtle);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-full);
  }

  :global(.extras-ready-icon) {
    width: var(--space-3);
    height: var(--space-3);
  }

  .extras-divider {
    height: 1px;
    background: var(--color-border);
    margin: 0 var(--space-4);
  }

  .extras-content {
    padding: var(--space-3) var(--space-4);
  }

  /* Discovery upsell styles moved to DeepResearchCTA.svelte */
</style>
