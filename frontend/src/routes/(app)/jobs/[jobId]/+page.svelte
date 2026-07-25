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
    XCircle,
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
  import { mapVerdict } from "$lib/types/publicCatalog";
  import type { Job, SolutionPreview, ReportSummary } from "$lib/types/job";
  import Button from "$lib/components/ui/Button.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";
  import SelectedSolutionsSummary from "$lib/components/SelectedSolutionsSummary.svelte";
  import DeliverableRow from "$lib/components/job/DeliverableRow.svelte";
  import CompletedAnalyst from "$lib/components/chat/CompletedAnalyst.svelte";
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
    const parts = ["Discovery run"];
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
  // Hidden-stage-adjusted counts so the aside matches JobCard / progress screen.
  const jobStageCounts = $derived(
    job ? getAdjustedStageCounts(job) : { completed: 0, total: 0 },
  );
  const localSolutions = $derived(clientSolutions ?? serverSolutions);
  const reportSummary = $derived(clientReportSummary ?? serverReportSummary);
  const discoveryData = $derived(clientDiscoveryData ?? serverDiscoveryData);
  const solutionVotes = $derived(clientSolutionVotes ?? serverSolutionVotes);
  const previewReport = $derived(clientPreviewReport ?? serverPreviewReport);
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
  let hasPlayedReveal = $state(false);
  let showReveal = $state(false);
  let summaryFetched = $state(false);
  let summaryLoading = $state(false);
  let discoveryShareOpen = $state(false);
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

  const jobId = $derived(page.params.jobId);
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

  const isRegenQueued = $derived(
    job?.status === 'QUEUED' &&
    (job?.solutionIdeas?.length ?? 0) > 0 &&
    !(job?.selectedSolutions?.length)
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
  const isGatePhase = $derived(
    job?.status === 'AWAITING_GATE' ||
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
          clientJob = sseData as Job;
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
        clientJob = { ...job, selectionDraft: d.selectionDraft };
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

  // "Generate more ideas" for the AWAITING_SELECTION zero-candidates case — same
  // regenerate-ideas call SelectionWorkbench's own regen button uses, just without
  // a ranked set to attach it to.
  async function regenerateFromEmpty() {
    if (!job || !jobId || regeneratingFromEmpty) return;
    regeneratingFromEmpty = true;
    regenerateFromEmptyError = "";
    try {
      await regenerateIdeas(jobId);
      clientJob = { ...job, status: 'QUEUED' };
    } catch (e) {
      if (e instanceof ApiError && e.status === 402) {
        const body = e.details as { balance?: number; required?: number } | undefined;
        creditTopUp.show({
          balance: body?.balance ?? (page.data.creditBalance as number) ?? 0,
          required: body?.required ?? (page.data.stageCosts as any)?.regenerate_ideas ?? 0,
          stageName: "idea regeneration",
        });
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
    if (!job || isResuming) return;
    isResuming = true;
    resumeError = "";
    try {
      const res = await fetch(`/api/jobs/${jobId}/resume`, { method: "POST" });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || "Failed to resume job");
      }
      const data = await res.json();
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
    if (!job || generatingLanding) return;
    generatingLanding = true;
    landingError = "";
    try {
      const res = await fetch(`/api/jobs/${jobId}/generate-landing`, { method: "POST" });
      if (!res.ok) {
        const data = await res.json();
        if (res.status === 402 && data.code === "INSUFFICIENT_CREDITS") {
          const landingCost = (page.data.stageCosts as any)?.landing_page ?? 5;
          creditTopUp.show({
            balance: data.balance ?? (page.data.creditBalance as number) ?? 0,
            required: landingCost,
            stageName: "landing page",
          });
          generatingLanding = false;
          return;
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
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || "Failed to cancel job");
      }
      clientJob = { ...job, status: "CANCELLED", errorMessage: "Cancelled by user" };
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
    hasPlayedReveal = d.job?.status === 'COMPLETED';
    showReveal = d.job?.status === 'COMPLETED';
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
      case "REGENERATING": return "Generating New Ideas";
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


  // Durable (survives a reload — see chatLedger.hasPendingSeed), not a parallel
  // client store: a chat-composed idea seed still being evaluated for THIS job.
  const seedPending = $derived(chatLedger.jobId === jobId && chatLedger.hasPendingSeed);

  // A SEED_IDEA claim flips job.status to QUEUED/RUNNING for the birth pipeline's
  // duration, exactly like a regen/gate round-trip — mirrors the gateApplyPending
  // idiom above: the workbench must stay mounted (with its own pending banner) so
  // beginSeedSettlementPoll/onSeedSettled keep running, instead of the progress
  // screen unmounting it out from under the in-flight seed.
  const seedRunning = $derived(seedPending && ['QUEUED', 'RUNNING'].includes(job?.status ?? ''));

  // Admin-granted optional decision tools, resolved fresh per navigation by
  // (app)/+layout.server.ts. Fails closed if the layout fetch didn't land.
  const decisionTools = $derived(page.data.featureAccess?.decisionTools === true);

  // ── Unified dashboard state ──
  const isSelectionPhase = $derived(
    ['AWAITING_SELECTION', 'REGENERATING'].includes(job?.status ?? '') || isRegenQueued || seedRunning
  );
  // Selection (G3) and guided-gate (G1/G2) phases share the same full-width,
  // aside-less hero/layout treatment — they're both "here's a checkpoint, review
  // it" screens rather than the running-research editorial hero.
  const isWorkbenchPhase = $derived(isSelectionPhase || isGatePhase);

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
    ['RUNNING', 'QUEUED', 'PENDING'].includes(job?.status ?? '') && !isRegenQueued && !isGatePhase && !seedRunning
  );
  const isGeneratingP2 = $derived(job?.status === 'RUNNING_PHASE2');
  const isGenerating = $derived(isGeneratingP1 || isGeneratingP2);

  // Section open state driven by lifecycle (passes to ExpandableSection defaultOpen)
  const discoveryOpen = $derived(isSelectionPhase);

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

  // A seed's settlement can add a brand-new pool candidate OR a brand-new ruled-out
  // entry that the SSE stream's sorted-name diff has no way to see (it only reconciles
  // NAMES it already knew about) — force both fetches rather than relying on SSE here.
  function handleSeedSettled() {
    void fetchSolutions();
    void loadPreviewReport(jobId ?? '');
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

  // Aside state for the editorial hero. Maps the live job status into one of
  // the JobHeroAside variants. Defaults to "running" while data is loading.
  const asideState = $derived<
    "running" | "queued" | "awaiting" | "regenerating" | "completed" | "failed" | "cancelled"
  >(
    !job
      ? "running"
      : job.status === "COMPLETED"
        ? "completed"
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

  $effect(() => {
    if (!isCompleted) return;
    if (untrack(() => hasPlayedReveal)) return;
    hasPlayedReveal = true;
    // Brief delay to let the last stage animate
    const timer = setTimeout(() => { showReveal = true; }, 500);
    return () => clearTimeout(timer);
  });

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
    if (untrack(() => summaryFetched)) return;
    summaryFetched = true;
    summaryLoading = true;
    getReportSummary(job!.id)
      .then(s => { clientReportSummary = s; })
      .catch(() => { /* fallback to simple card */ })
      .finally(() => { summaryLoading = false; });
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
      mode={isSelectionPhase ? 'selection' : isGatePhase ? 'gate' : 'default'}
      jobId={jobId ?? undefined}
      toolTasks={selectionToolTasks}
      selectedCount={sidebarSelectedCount}
      availableSectionIds={isSelectionPhase ? dossier.availableSectionIds : undefined}
      chatMode={job.chatMode ?? false}
      gateStage={job.gateStage ?? null}
      {decisionTools}
    />
  {/if}
  <!-- div, not <main>: the (app) layout already renders the page's single landmark <main>. -->
  <div class="job-page-content" class:job-page-content--selection={isWorkbenchPhase}>
    <AnnotationProvider mode="owner" enabled={['AWAITING_SELECTION', 'REGENERATING'].includes(job?.status ?? '')} jobId={jobId ?? undefined}>
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
      <div class="job-hero-grid" class:job-hero-grid--selection={isWorkbenchPhase}>
        <div class="job-hero-main" data-annotation-anchor="research-header">
          <PageHeader
            class={isWorkbenchPhase ? 'job-selection-header' : ''}
            icon={isWorkbenchPhase ? undefined : Telescope}
            breadcrumbItems={[{ label: 'Dashboard', href: '/dashboard' }]}
            breadcrumbCurrent={isSelectionPhase ? SHORTLIST_TITLE : isGatePhase ? 'Checkpoint' : titleCase(nicheName) || 'Research'}
            title={pageTitle}
            titleVariant={isSelectionPhase ? 'research-topic' : 'default'}
            subtitle={isSelectionPhase ? selectionSubtitle : isGatePhase ? gateSubtitle : undefined}
          >
            {#snippet metadata()}
              {#if job && nicheName !== job.niche}
                <p class="mt-1 text-sm text-text-muted truncate" title={job.niche}>
                  {job.niche.length > 100 ? job.niche.substring(0, 100) + '...' : job.niche}
                </p>
              {/if}
              {#if cancelError}
                <div class="mt-2 text-sm text-error">{cancelError}</div>
              {/if}
            {/snippet}
            {#snippet actions()}
              <div class="flex items-center gap-3 w-full sm:w-auto justify-end">
                <TourRestartButton />
                {#if isCompleted && reportAsset}
                  <Button href="/jobs/{job.id}/report" icon={REPORT_ICON} label="View Report" class="btn-primary btn-sm" />
                {/if}
                {#if isSelectionPhase && displaySolutions.length > 0}
                  <button
                    onclick={() => (discoveryShareOpen = true)}
                    class="btn-ghost share-discovery-btn"
                    aria-label="Share discovery"
                  >
                    <Share2 class="w-3.5 h-3.5" />
                    <span>Share</span>
                  </button>
                {/if}
                {#if !isWorkbenchPhase}
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
        </div>
        {#if !isWorkbenchPhase}
          <aside class="job-hero-aside">
            <JobHeroAside
              state={asideState}
              progressPercent={job.progressPercent}
              stagesCompleted={jobStageCounts.completed}
              totalStages={jobStageCounts.total}
              startedAt={job.startedAt}
              selectionCount={displaySolutions.length}
              summary={reportSummary}
              errorDetails={job.errorDetails}
              errorMessage={job.errorMessage}
              stopReason={job.stopReason}
              stopReasonDetails={job.stopReasonDetails}
              creditRefunded={job.creditRefunded}
            />
          </aside>
        {/if}
      </div>

      {#if !isWorkbenchPhase}
        <!-- ═══ PROGRESS STEPPER ═══ -->
        <ProgressStepper
          currentStep={stepperStep}
          {discussionCount}
          painPointCount={previewPainPointCount}
          solutionCount={displaySolutions.length}
        />
      {/if}

      <!-- ═══ ERROR / CANCELLED / RESUME ═══ -->
      {#if job.status === 'CANCELLED'}
        <div class="p-4 rounded-lg bg-bg-elevated border border-border mb-6">
          <div class="flex items-start gap-3">
            <div class="p-2 rounded-lg bg-text-muted/10 shrink-0">
              <XCircle class="w-5 h-5 text-text-muted" />
            </div>
            <div class="flex-1">
              <h3 class="text-sm font-medium text-text-secondary">Research Cancelled</h3>
              <p class="mt-1 text-sm text-text-muted">This research was cancelled. Your credits have been refunded.</p>
              <button onclick={() => goto(`/new?fromJob=${job.id}&prefilled=${encodeURIComponent(job.niche)}`)} class="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-accent hover:text-accent-hover transition-colors">
                Start new research <ArrowRight class="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      {/if}

      {#if job.status === 'FAILED' && job.stopReason === 'INSUFFICIENT_DATA'}
        <div class="p-5 rounded-lg bg-warning/5 border border-warning/20 mb-6">
          <div class="flex items-start gap-4">
            <div class="p-2.5 rounded-xl bg-warning/10 border border-warning/20 shrink-0">
              <AlertTriangle class="w-6 h-6 text-warning" />
            </div>
            <div class="flex-1">
              <h3 class="text-base font-semibold text-text-primary">Not Enough Data Found</h3>
              <p class="mt-1.5 text-sm text-text-secondary">
                {job.stopReasonDetails?.recommendation || 'The research could not continue due to insufficient discussion data.'}
              </p>
              <div class="mt-4 flex items-center gap-2" style="color: var(--color-success-dark)">
                <CheckCircle class="w-4 h-4" />
                <span class="text-sm">Credits refunded automatically</span>
              </div>
            </div>
          </div>
        </div>
      {:else if job.status === 'FAILED' && (job.errorDetails || job.errorMessage)}
        <div class="p-4 rounded-lg bg-error/5 border border-error/20 mb-6">
          <div class="flex items-start gap-3">
            <div class="p-2 rounded-lg bg-error/10 shrink-0">
              <XCircle class="w-5 h-5 text-error" />
            </div>
            <div class="flex-1">
              {#if job.errorDetails}
                <h3 class="text-sm font-medium text-error">{job.errorDetails.userMessage}</h3>
                <p class="mt-1 text-sm text-text-muted">{job.errorDetails.actionableGuidance}</p>
              {:else}
                <h3 class="text-sm font-medium text-error">Error</h3>
                <p class="mt-1 text-sm text-text-muted">{job.errorMessage}</p>
              {/if}
            </div>
          </div>
        </div>
      {/if}

      {#if job.status === 'FAILED'}
        <div class="card p-6 mb-6">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 class="text-sm font-medium text-text-primary">Resume from Checkpoint</h3>
              <p class="mt-1 text-sm text-text-muted">Continue where you left off.</p>
            </div>
            <SubmitButton onclick={resumeJob} loading={isResuming} loadingText="Resuming..." icon={RotateCw} keepIconOnLoad label="Resume" class="btn-primary flex items-center gap-2" />
          </div>
          {#if resumeError}
            <p class="mt-3 text-sm text-error">{resumeError}</p>
          {/if}
        </div>
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

        {#if isSelectionPhase && (displaySolutions.length > 0 || examinedRuledOut.length > 0 || seedPending)}
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
            isRegenerating={job.status === 'REGENERATING' || isRegenQueued}
            selectedSolutions={job.selectedSolutions ?? undefined}
            selectedSolutionIds={job.selectedSolutionIds ?? undefined}
            decisionProfile={job.selectionDecisionProfile ?? null}
            {solutionVotes}
            onComplete={handleSelectionComplete}
            onRegenerateStart={() => { clientJob = { ...job!, status: 'QUEUED' }; }}
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
                  loading={regeneratingFromEmpty}
                  loadingText="Generating..."
                  label="Generate more ideas"
                  class="btn-primary mt-6 inline-block"
                />
                {#if regenerateFromEmptyError}
                  <p class="mt-3 text-sm text-error">{regenerateFromEmptyError}</p>
                {/if}
              {:else}
                <button onclick={() => goto(`/new?fromJob=${job.id}&prefilled=${encodeURIComponent(job.niche)}`)} class="mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-accent hover:text-accent-hover transition-colors">
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

        {#if previewReport || discoveryData || discoveryFetchFailed || previewFetchFailed}
          <div class="discovery-sections" class:discovery-dossier={isSelectionPhase} data-annotation-anchor="research-dossier">
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
            {#if isSelectionPhase}
              <div class="dossier-header">
                <div>
                  <p class="dossier-eyebrow">Discovery dossier</p>
                  <h2 class="dossier-title">Evidence behind the shortlist</h2>
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
        {:else if reportSummary}
          <!-- ═══ COMPLETED: Report summary cards ═══ -->
          {@const verdictNorm = mapVerdict(reportSummary.verdict)}
          <div class="report-summary-card">
            <div class="report-summary-header">
              <div>
                <p class="report-summary-eyebrow">Report ready</p>
                <h2 class="report-summary-title">Your research is complete</h2>
              </div>
              <Button href="/jobs/{job.id}/report" icon={REPORT_ICON} label="View Full Report" class="btn-primary btn-sm" />
            </div>
            <div class="report-summary-metrics">
              {#if reportSummary.opportunity_score != null}
                <div class="report-metric">
                  <span class="report-metric-value">{reportSummary.opportunity_score > 1 ? reportSummary.opportunity_score : Math.round(reportSummary.opportunity_score * 100)}</span>
                  <span class="report-metric-label">Score</span>
                </div>
              {/if}
              {#if verdictNorm}
                <div class="report-metric">
                  <span class="report-metric-value report-metric-value--{verdictNorm === 'GO' ? 'success' : verdictNorm === 'NO-GO' ? 'error' : 'warning'}">{verdictNorm}</span>
                  <span class="report-metric-label">Verdict</span>
                </div>
              {/if}
              {#if reportSummary.total_keywords != null}
                <div class="report-metric">
                  <span class="report-metric-value">{reportSummary.total_keywords}</span>
                  <span class="report-metric-label">Keywords</span>
                </div>
              {/if}
              {#if reportSummary.competitor_count != null}
                <div class="report-metric">
                  <span class="report-metric-value">{reportSummary.competitor_count}</span>
                  <span class="report-metric-label">Competitors</span>
                </div>
              {/if}
            </div>
          </div>
        {/if}

        <!-- ═══ EXTRAS ═══ -->
        {#if isCompleted}
          <div class="extras-card">
            <div class="extras-header">
              <div class="extras-header-left">
                <div class="extras-icon-box"><Package class="extras-icon" /></div>
                <div class="extras-title-group">
                  <span class="extras-title">Extras</span>
                  <span class="extras-subtitle">Add-on deliverables</span>
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
                asset={landingAsset}
                generating={generatingLanding}
                error={landingError}
                onGenerate={generateLanding}
              />
            </div>
          </div>
        {/if}
      {/if}

      {#if isCompleted}
        <CompletedAnalyst jobId={job.id} compact />
      {/if}

      <!-- ═══ RUN PROVENANCE ═══ -->
      <div class="mt-6 p-4 rounded-lg bg-bg-surface border border-border">
        <div class="run-meta">
          <span class="run-meta__timeline">
            <span class="run-meta__dot" class:run-meta__dot--done={job.completedAt}></span>
            <span>{runTimeline}</span>
          </span>
          <button type="button" class="run-meta__id" onclick={copyRunId} aria-label="Copy full run ID">
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
  <ShareDiscoveryModal bind:open={discoveryShareOpen} jobId={jobId} />
{/if}

<!-- First-run tutorial. `selectionToolTasks !== undefined` is the signal that the
     CLIENT-side decision-state fetch landed: until it does, the shortlist dock has not
     mounted and the guide card still reads "Updating your next useful step…", so two of
     the five steps would have nothing to point at. -->
<TourHost
  chapter="job-shortlist"
  enabled={decisionTools}
  ready={isSelectionPhase
    && displaySolutions.length > 0
    && !solutionsLoading
    && selectionToolTasks !== undefined}
  deferred={seedRunning || isRegenQueued || invalidSolutionCount > 0}
  reflowKey={selectionToolTasks}
/>

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
    gap: 0.5rem 1rem;
  }
  .run-meta__timeline {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.75rem;
    line-height: 1.4;
    color: var(--color-text-secondary);
  }
  .run-meta__dot {
    flex-shrink: 0;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: color-mix(in srgb, var(--color-text-muted) 55%, transparent);
  }
  .run-meta__dot--done {
    background: var(--color-success);
  }
  .run-meta__id {
    display: inline-flex;
    align-items: center;
    gap: 0.42rem;
    padding: 0.26rem 0.5rem 0.26rem 0.42rem;
    border: 1px solid var(--color-border);
    border-radius: 0.375rem;
    background: var(--color-bg-elevated);
    color: var(--color-text-secondary);
    font-size: 0.75rem;
    cursor: pointer;
    transition: border-color 0.15s ease, color 0.15s ease;
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
    font-size: 0.5625rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }
  .run-meta__id code {
    font-family: var(--font-mono);
    letter-spacing: 0.01em;
  }
  .run-meta__id :global(.run-meta__id-icon) {
    width: 0.8rem;
    height: 0.8rem;
    color: var(--color-text-muted);
  }
  .run-meta__id :global(.run-meta__id-icon--done) {
    color: var(--color-success);
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
    gap: 0.8rem;
  }

  :global(.job-selection-header .page-header-title-row) {
    min-width: 0;
    gap: 0.78rem;
  }

  :global(.job-selection-header .page-header-actions) {
    justify-self: end;
    padding-top: 0;
  }

  :global(.job-selection-header .page-header-title-row > div:first-child) {
    padding: 0.42rem;
    border-radius: 0.75rem;
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
    margin-bottom: 0.2rem;
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

  /* ═══ Section intro ═══ */
  .section-intro {
    max-width: 74ch;
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    line-height: 1.55;
    margin: 0 0 0.72rem;
    text-wrap: pretty;
  }

  .section-footnote {
    margin: 0.72rem 0 0;
    padding-top: 0.7rem;
    border-top: 1px solid color-mix(in srgb, var(--color-border) 72%, transparent);
    color: var(--color-text-muted);
    font-size: 0.75rem;
    line-height: 1.42;
    text-wrap: pretty;
  }

  /* ═══ Methodology footnote ═══ */
  .methodology-note {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    color: var(--color-text-muted);
    letter-spacing: 0.02em;
    margin: 0.78rem 0 0;
    padding-top: 0.72rem;
    border-top: 1px solid var(--color-border);
  }

  /* .preview-capped* classes moved to src/lib/styles/preview-capped.css
     (global; shared with SharedDiscoveryView). */

  /* ═══ Report summary (completed state) ═══ */
  .report-summary-card {
    padding: 1.5rem;
    margin-bottom: 1rem;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border-success);
    border-radius: 0.75rem;
  }

  .report-summary-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1.25rem;
    gap: 1rem;
  }

  .report-summary-eyebrow {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-accent);
    margin: 0 0 0.25rem;
  }

  .report-summary-title {
    font-family: var(--font-display);
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--color-text-primary);
    margin: 0;
  }

  .report-summary-metrics {
    display: flex;
    gap: 2rem;
    flex-wrap: wrap;
  }

  .report-metric {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
  }

  .report-metric-value {
    font-family: var(--font-mono);
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--color-accent);
    font-variant-numeric: tabular-nums;
    line-height: 1;
  }

  .report-metric-value--success {
    color: var(--color-success);
  }

  .report-metric-value--warning {
    color: var(--color-warning);
  }

  .report-metric-value--error {
    color: var(--color-error);
  }

  .report-metric-label {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 500;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  /* gate-locked and stage-list removed - no longer used in unified dashboard */

  /* ═══ Responsive ═══ */
  @media (max-width: 639px) {
    .report-summary-header {
      flex-direction: column;
      align-items: flex-start;
    }

    .report-summary-metrics {
      gap: 1rem;
    }
  }

  /* ── Extras card ── */
  .extras-card {
    margin-top: 1rem;
    padding: 0;
    border-radius: 0.75rem;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    overflow: hidden;
  }

  /* extras-card--locked removed - extras only shown when complete */

  .extras-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.875rem 1rem;
  }

  .extras-header-left {
    display: flex;
    align-items: center;
    gap: 0.625rem;
  }

  .extras-icon-box {
    width: 1.75rem;
    height: 1.75rem;
    border-radius: 0.5rem;
    background: var(--color-accent-subtle);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  :global(.extras-icon) {
    width: 0.875rem;
    height: 0.875rem;
    color: var(--color-accent);
  }

  .extras-title-group {
    display: flex;
    flex-direction: column;
    gap: 0.0625rem;
  }

  .extras-title {
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--color-text-primary);
    line-height: 1.2;
  }

  .extras-subtitle {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    line-height: 1.3;
  }

  .extras-ready-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--color-success);
    background: var(--color-success-subtle);
    padding: 0.1875rem 0.5rem;
    border-radius: 9999px;
  }

  :global(.extras-ready-icon) {
    width: 0.75rem;
    height: 0.75rem;
  }

  .extras-divider {
    height: 1px;
    background: var(--color-border);
    margin: 0 1rem;
  }

  .extras-content {
    padding: 0.75rem 1rem;
  }

  /* Discovery upsell styles moved to DeepResearchCTA.svelte */
</style>
