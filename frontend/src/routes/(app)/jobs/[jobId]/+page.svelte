<script lang="ts">
  import { untrack } from "svelte";
  import { page } from "$app/state";
  import { goto, invalidateAll } from "$app/navigation";
  import {
    subscribeToProgress,
    shouldKeepSSEOpen,
    getReportSummary,
    getDiscoveryShareStatus,
  } from "$lib/api";
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
  import { getAdjustedStageCounts } from "$lib/utils/stages";
  import { mapVerdict } from "$lib/types/publicCatalog";
  import type { Job, SolutionPreview, ReportSummary } from "$lib/types/job";
  import Button from "$lib/components/ui/Button.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";
  import SelectedSolutionsSummary from "$lib/components/SelectedSolutionsSummary.svelte";
  import DeliverableRow from "$lib/components/job/DeliverableRow.svelte";
  import JobHeroAside from "$lib/components/job/JobHeroAside.svelte";

  // Preview / Dashboard components
  import PhaseNav from "$lib/components/nav/PhaseNav.svelte";
  import ExpandableSection from "$lib/components/ui/ExpandableSection.svelte";
  import PreviewOverview from "$lib/components/preview/PreviewOverview.svelte";
  import ProgressStepper from "$lib/components/preview/ProgressStepper.svelte";
  import PainPointSummaryCard from "$lib/components/preview/PainPointSummaryCard.svelte";
  import AudienceSnapshot from "$lib/components/preview/AudienceSnapshot.svelte";
  import CommunitySourcesSection from "$lib/components/preview/CommunitySourcesSection.svelte";
  import SelectionWorkbench from "$lib/components/selection/SelectionWorkbench.svelte";
  import ResearchProgressScreen from "$lib/components/preview/ResearchProgressScreen.svelte";

  import DeepResearchCTABlock from "$lib/components/preview/DeepResearchCTABlock.svelte";
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
  import ShareDiscoveryModal from "$lib/components/ShareDiscoveryModal.svelte";
  import type { DiscoveryData } from "$lib/types/discovery";
  import type { PreviewReport } from "$lib/types/previewReport";
  import { getDiscoveryData, getPreviewReport } from "$lib/api";

  let { data } = $props();

  // ── Server data (reactive via $derived, updates on navigation/invalidateAll) ──
  const serverJob = $derived(data.job as Job | null);
  const serverSolutions = $derived((data.solutions ?? null) as SolutionPreview[] | null);
  const serverReportSummary = $derived((data.reportSummary ?? null) as ReportSummary | null);
  const serverDiscoveryData = $derived((data.discoveryData ?? null) as DiscoveryData | null);
  const serverSolutionVotes = $derived((data.solutionVotes ?? {}) as Record<string, number>);
  const serverPreviewReport = $derived((data.previewReport ?? null) as PreviewReport | null);

  // ── Client overrides (SSE updates, async fetches) ──
  let clientJob = $state<Job | null>(null);
  let clientSolutions = $state<SolutionPreview[] | null>(null);
  let clientReportSummary = $state<ReportSummary | null>(null);
  let clientDiscoveryData = $state<DiscoveryData | null>(null);
  let clientSolutionVotes = $state<Record<string, number> | null>(null);
  let clientPreviewReport = $state<PreviewReport | null>(null);

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

  const jobId = $derived(page.params.jobId);

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
        if (sseData && sseData.id) {
          clientJob = sseData as Job;
          if (sseData.solutionIdeas) {
            const incoming = sseData.solutionIdeas as SolutionPreview[];
            const incomingNames = incoming.map((s) => s.solution_name).sort().join('|');
            const currentNames = (localSolutions ?? []).map((s) => s.solution_name).sort().join('|');
            if (incomingNames !== currentNames) {
              clientSolutions = incoming;
            }
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
      clientSolutionVotes = info.isShared && info.solutionVotes ? info.solutionVotes : {};
    } catch {}
  }

  async function loadDiscoveryData(id: string) {
    if (discoveryLoading) return;
    discoveryLoading = true;
    try { clientDiscoveryData = await getDiscoveryData(id); }
    catch { /* graceful fallback - old jobs won't have this asset */ }
    finally { discoveryLoading = false; }
  }

  let previewReportLoading = $state(false);
  async function loadPreviewReport(id: string) {
    if (previewReportLoading) return;
    previewReportLoading = true;
    try { clientPreviewReport = await getPreviewReport(id); }
    catch { /* graceful fallback - old jobs won't have preview report */ }
    finally { previewReportLoading = false; }
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

    // Reset UI state
    loading = false;
    error = "";
    discoveryLoading = false;
    summaryFetched = !!d.reportSummary;
    hasPlayedReveal = d.job?.status === 'COMPLETED';
    showReveal = d.job?.status === 'COMPLETED';
    lastHandledStatus = d.job?.status ?? '';

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
    if (status === lastHandledStatus) return;
    lastHandledStatus = status;

    if (['AWAITING_SELECTION', 'REGENERATING'].includes(status)) {
      if (!localSolutions || localSolutions.length === 0) {
        getSolutions(jobId)
          .then(d => { clientSolutions = d.solutionIdeas ?? null; })
          .catch(() => { clientSolutions = currentJob.solutionIdeas ?? null; });
      }
      pollVotes(jobId);
      loadDiscoveryData(jobId);
      loadPreviewReport(jobId);
    }

    if (['COMPLETED', 'FAILED', 'RUNNING_PHASE2'].includes(status)) {
      loadDiscoveryData(jobId);
      loadPreviewReport(jobId);
    }
  });

  function getStatusVariant(status: string): "success" | "warning" | "error" | "muted" | "info" | "accent" {
    switch (status) {
      case "COMPLETED": return "success";
      case "RUNNING": case "RUNNING_PHASE2": return "info";
      case "FAILED": return "error";
      case "CANCELLED": return "muted";
      case "AWAITING_SELECTION": return "accent";
      case "REGENERATING": return "warning";
      default: return "warning";
    }
  }

  function getStatusLabel(status: string): string {
    switch (status) {
      case "AWAITING_SELECTION": return "Ready for Selection";
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


  // ── Unified dashboard state ──
  const isSelectionPhase = $derived(
    ['AWAITING_SELECTION', 'REGENERATING'].includes(job?.status ?? '') || isRegenQueued
  );
  const isGeneratingP1 = $derived(
    ['RUNNING', 'QUEUED', 'PENDING'].includes(job?.status ?? '') && !isRegenQueued
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
    previewReport?.niche?.slice(0, 60) ??
    job?.niche?.slice(0, 60) ??
    ''
  );
  const pageTitle = $derived(
    isSelectionPhase
      ? 'Select candidates for Deep Research'
      : titleCase(nicheName) || 'Research Progress',
  );

  const selectionSubtitle = $derived(
    `${sentenceHeading(nicheName)}. Discovery found ${displaySolutions.length} ranked ${displaySolutions.length === 1 ? 'candidate' : 'candidates'}. Choose up to 3 for validation.`,
  );

  const discussionCount = $derived(
    (previewReport?.research_metadata?.filtering_stats as Record<string, number>)?.total_urls_relevant ??
    (((previewReport?.research_metadata?.reddit_posts_analyzed ?? 0) +
     (previewReport?.research_metadata?.twitter_threads_analyzed ?? 0) +
     (previewReport?.research_metadata?.generic_posts_analyzed ?? 0)) || 0)
  );

  const previewPainPointCount = $derived(
    previewReport?.pain_point_analytics?.total_pain_points ??
    previewReport?.detailed_pain_points?.length ?? 0
  );

  const segmentCount = $derived(
    previewReport?.audience_mapping?.audience_segments?.length ?? 0
  );

  // Portfolio-funnel: findings examined but not carried forward (demoted winners, rejected
  // backfill candidates) + groups of surviving ideas that are variants of one product.
  const examinedRuledOut = $derived(previewReport?.examined_ruled_out ?? []);
  const overlapGroups = $derived(previewReport?.overlap_groups ?? []);
  const marketReality = $derived(previewReport?.market_reality ?? null);

  // Placeholder data for locked sections - use short niche name, not full description
  const niche = $derived(previewReport?.niche ?? job?.niche ?? '');
  const placeholderNiche = $derived(stripLeadingArticle(nicheName || niche));
  const placeholderExec = $derived(placeholderExecutiveDashboard(placeholderNiche));
  const placeholderComp = $derived(placeholderCompetitors(placeholderNiche));

  // Real top pain point for preview hero (correct 0-1 scale)
  const topRealPain = $derived(
    (previewReport?.detailed_pain_points ?? [])
      .slice()
      .sort((a: any, b: any) => (b.severity_score ?? 0) - (a.severity_score ?? 0))[0] ?? null
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

  // All pain points sorted by severity
  const topPainPoints = $derived(
    (previewReport?.detailed_pain_points ?? [])
      .slice()
      .sort((a, b) => b.severity_score - a.severity_score)
  );
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
      mode={isSelectionPhase ? 'selection' : 'default'}
      selectionCount={displaySolutions.length}
      selectedCount={job.selectedSolutions?.length ?? 0}
    />
  {/if}
  <main class="job-page-content" class:job-page-content--selection={isSelectionPhase}>
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
          phase={isGeneratingP1 ? 'discovery' : 'deep_research'}
          jobStatus={job.status}
          niche={job.niche}
          entryMode={job.entryMode}
          userEmail={data.userEmail}
          progressPercent={job.progressPercent}
          stagesCompleted={job.stagesCompleted ?? 0}
          totalStages={job.totalStages ?? 0}
          currentStage={job.currentStage}
          queuePosition={job.queuePosition ?? undefined}
          catalogPainPoints={data.catalogPainPoints ?? []}
          selectedNames={job.selectedSolutions ?? []}
          solutionIdeas={job.solutionIdeas ?? []}
          primaryWinner={job.selectedSolution}
          onCancel={isGeneratingP1 ? cancelJob : undefined}
          {cancelling}
        />
      {:else}
      <!-- ═══ EDITORIAL HERO (1fr | 320px grid) ═══ -->
      <div class="job-hero-grid" class:job-hero-grid--selection={isSelectionPhase}>
        <div class="job-hero-main">
          <PageHeader
            class={isSelectionPhase ? 'job-selection-header' : ''}
            icon={isSelectionPhase ? undefined : Telescope}
            breadcrumbItems={[{ label: 'Dashboard', href: '/dashboard' }]}
            breadcrumbCurrent={isSelectionPhase ? 'Selection' : titleCase(nicheName) || 'Research'}
            title={pageTitle}
            subtitle={isSelectionPhase ? selectionSubtitle : undefined}
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
                {#if isCompleted && reportAsset}
                  <Button href="/jobs/{job.id}/report" icon={REPORT_ICON} label="View Report" class="btn-primary btn-sm" />
                {/if}
                {#if isSelectionPhase && displaySolutions.length > 0}
                  <button
                    onclick={() => (discoveryShareOpen = true)}
                    class="share-discovery-btn"
                    aria-label="Share discovery"
                  >
                    <Share2 class="w-3.5 h-3.5" />
                    <span>Share</span>
                  </button>
                {/if}
                {#if !isSelectionPhase}
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
        {#if !isSelectionPhase}
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

      {#if !isSelectionPhase}
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

        {#if isSelectionPhase && displaySolutions.length > 0}
          <SelectionWorkbench
            jobId={jobId ?? ''}
            solutions={displaySolutions}
            coverageNotes={previewReport?.data_quality_summary?.quality_caveats ?? []}
            {examinedRuledOut}
            {overlapGroups}
            {marketReality}
            ideaPortfolioSummary={previewReport?.idea_portfolio_summary ?? null}
            {discussionCount}
            painPointCount={previewPainPointCount}
            {segmentCount}
            creditBalance={page.data.creditBalance ?? 0}
            stageCosts={page.data.stageCosts ?? { discovery: 5, deep_research: 15, landing_page: 5, regenerate_ideas: 2 }}
            canRegenerate={job.canRegenerate ?? false}
            isRegenerating={job.status === 'REGENERATING' || isRegenQueued}
            selectedSolutions={job.selectedSolutions ?? undefined}
            {solutionVotes}
            onComplete={handleSelectionComplete}
            onRegenerateStart={() => { clientJob = { ...job!, status: 'QUEUED' }; }}
          />
        {/if}

        {#if previewReport || discoveryData}
          <div class="discovery-sections" class:discovery-dossier={isSelectionPhase}>
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
                    <dt>Sources</dt>
                    <dd>{discoveryData?.subreddit_names?.length ?? 0}</dd>
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
                  nicheName={nicheName}
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
                    solutionIdeas={job.solutionIdeas ?? []}
                    primaryWinner={job.selectedSolution}
                    status={job.status}
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
                  postsAnalyzed={discussionCount}
                  subredditCount={discoveryData.subreddit_names?.length ?? 0}
                  totalEngagement={discoveryData.methodology?.total_engagement ?? 0}
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
                <p class="section-intro">The highest-signal pain clusters from discovery, ranked by severity and commercial intent.</p>
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
                count={discoveryData?.subreddit_names?.length ?? 0}
                countSuffix="sources"
                variant={isSelectionPhase ? "default" : "success"}
                defaultOpen={false}
                resetKey={sectionResetKey}
                id="community"
              >
                <CommunitySourcesSection
                  subredditNames={discoveryData?.subreddit_names}
                  communityHubs={previewReport?.audience_mapping?.community_hubs}
                  postsAnalyzed={((previewReport?.research_metadata?.reddit_posts_analyzed ?? 0) + (previewReport?.research_metadata?.generic_posts_analyzed ?? 0)) || undefined}
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
        {#if !isCompleted && !isSelectionPhase}
          <!-- Capped preview: UnifiedHero with real blurred content -->
          <div class="preview-capped">
            <UnifiedHero
              report={previewHeroReport}
              nicheName={nicheName}
              nicheDescription={previewReport?.niche_context?.niche_description ?? `Analysis of the ${niche} market`}
              funnelStats={realFunnelStats}
              previewMode={true}
            />
            <div class="preview-capped-fade"></div>
            <div class="preview-capped-label">
              <span class="preview-capped-badge">Unlocks with Deep Research</span>
            </div>
          </div>

          <!-- SEO Keywords preview - editorial hairline insert between capped cards -->
          <SEOKeywordsPreview nicheName={placeholderNiche} />

          <!-- Capped preview: Competitors with real blurred content -->
          <div class="preview-capped preview-capped--sm">
            <Competitors
              profiles={placeholderComp.profiles}
              analysis={placeholderComp.analysis}
              analytics={placeholderComp.analytics}
              selectedSolutionName={`${placeholderNiche} Opportunity Analyzer`}
              previewMode={true}
            />
            <div class="preview-capped-fade"></div>
            <div class="preview-capped-label">
              <span class="preview-capped-badge">Unlocks with Deep Research</span>
            </div>
          </div>

          <!-- Deep Research CTA with pricing -->
          {#if isSelectionPhase}
            <DeepResearchCTABlock
              creditCost={page.data.stageCosts?.deep_research ?? 15}
              onUnlock={scrollToSolutions}
            />
          {/if}
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
  </main>
</div>

{#if jobId}
  <ShareDiscoveryModal bind:open={discoveryShareOpen} jobId={jobId} />
{/if}

<style>
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
    color: var(--color-text-muted);
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

  /* Share discovery button (header actions) */
  .share-discovery-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.375rem 0.75rem;
    font-family: var(--font-body);
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--color-text-secondary);
    background: transparent;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md, 0.5rem);
    cursor: pointer;
    transition:
      transform 220ms cubic-bezier(0.32, 0.72, 0, 1),
      color 220ms cubic-bezier(0.32, 0.72, 0, 1),
      border-color 220ms cubic-bezier(0.32, 0.72, 0, 1),
      background-color 220ms cubic-bezier(0.32, 0.72, 0, 1);
  }
  .share-discovery-btn:hover {
    color: var(--color-text-primary);
    border-color: var(--color-border-emphasis);
    background: var(--color-bg-surface);
  }
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

  .discovery-sections {
    margin-top: 1.1rem;
  }

  .discovery-dossier {
    position: relative;
    margin-top: 1.18rem;
    padding: 0.62rem;
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 46%, transparent);
    border-radius: var(--radius-xl);
    background:
      color-mix(in srgb, var(--color-bg-surface) 78%, var(--color-bg-elevated));
    box-shadow: var(--shadow-sm);
  }

  .dossier-header {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: end;
    gap: 1rem;
    padding: 0.82rem 0.92rem 0.92rem;
    border-bottom: 1px solid color-mix(in srgb, var(--color-border-emphasis) 46%, transparent);
  }

  .dossier-eyebrow {
    margin: 0 0 0.24rem;
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 800;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  .dossier-title {
    margin: 0;
    color: var(--color-text-primary);
    font-family: var(--font-display);
    font-size: clamp(1rem, 1.16vw, 1.125rem);
    font-weight: 800;
    line-height: 1.16;
    letter-spacing: -0.01em;
  }

  .dossier-copy {
    max-width: 58ch;
    margin: 0.34rem 0 0;
    color: var(--color-text-secondary);
    font-size: 0.75rem;
    line-height: 1.46;
    text-wrap: pretty;
  }

  .dossier-ledger {
    display: grid;
    grid-template-columns: repeat(3, minmax(4.8rem, 1fr));
    gap: 0.28rem;
    min-width: 16.5rem;
    margin: 0;
    padding: 0.28rem;
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 38%, transparent);
    border-radius: 0.75rem;
    background: color-mix(in srgb, var(--color-bg-elevated) 74%, transparent);
  }

  .dossier-ledger div {
    display: grid;
    gap: 0.1rem;
    min-width: 0;
    padding: 0.4rem 0.46rem;
    border-radius: 0.5rem;
    background: color-mix(in srgb, white 58%, transparent);
  }

  .dossier-ledger dt {
    color: var(--color-text-muted);
    font-size: 0.5625rem;
    font-weight: 700;
    line-height: 1;
  }

  .dossier-ledger dd {
    margin: 0;
    color: var(--color-text-primary);
    font-family: var(--font-mono);
    font-size: 0.875rem;
    font-weight: 800;
    line-height: 1.1;
    font-variant-numeric: tabular-nums;
  }

  :global(.job-page-content--selection .section-container.expandable) {
    margin-top: 0.82rem;
    margin-bottom: 0.92rem;
    overflow: visible;
    border: 0;
    border-radius: 0;
    background: transparent;
  }

  :global(.job-page-content--selection .section-container.expandable.elevated) {
    background: transparent;
  }

  :global(.job-page-content--selection .section-container.expandable .expandable-trigger) {
    padding: 0.72rem 0.08rem 0.62rem;
    border-top: 1px solid color-mix(in srgb, var(--color-border-emphasis) 54%, transparent);
    border-radius: 0;
    background: transparent;
    transition:
      color 240ms cubic-bezier(0.32, 0.72, 0, 1),
      transform 240ms cubic-bezier(0.32, 0.72, 0, 1);
  }

  :global(.job-page-content--selection .section-container.expandable .expandable-trigger:hover) {
    background: color-mix(in srgb, var(--color-bg-surface) 60%, transparent);
  }

  :global(.job-page-content--selection .section-container.expandable .section-header-title) {
    font-size: 0.9375rem;
    font-weight: 800;
  }

  :global(.job-page-content--selection .section-container.expandable .section-body) {
    transition: grid-template-rows 320ms cubic-bezier(0.32, 0.72, 0, 1);
  }

  :global(.job-page-content--selection .section-container.expandable .section-body-inner) {
    overflow: hidden;
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 52%, transparent);
    border-radius: 0.875rem;
    background:
      color-mix(in srgb, var(--color-bg-elevated) 94%, var(--color-bg-surface));
    box-shadow:
      0 18px 48px rgba(24, 24, 27, 0.045);
  }

  :global(.job-page-content--selection .section-container.expandable .section-content) {
    padding: 0.98rem 1.08rem 1.08rem !important;
  }

  :global(.job-page-content--selection .section-container.expandable .chevron-icon) {
    transition: transform 260ms cubic-bezier(0.32, 0.72, 0, 1);
  }

  :global(.discovery-dossier .section-container.expandable) {
    margin: 0;
  }

  :global(.discovery-dossier .section-container.expandable .expandable-trigger) {
    padding: 0.78rem 0.5rem;
    border-top: 0;
    border-bottom: 1px solid color-mix(in srgb, var(--color-border-emphasis) 38%, transparent);
  }

  :global(.discovery-dossier .section-container.expandable:last-child .expandable-trigger) {
    border-bottom-color: transparent;
  }

  :global(.discovery-dossier .section-container.expandable .header-content) {
    gap: 0.48rem;
  }

  :global(.discovery-dossier .section-container.expandable .section-icon) {
    width: 0.82rem;
    height: 0.82rem;
    color: var(--color-text-muted);
  }

  :global(.discovery-dossier .section-container.expandable .section-header-title) {
    display: inline-flex;
    align-items: baseline;
    gap: 0.46rem;
    font-size: 0.8125rem;
    font-weight: 800;
    letter-spacing: -0.005em;
  }

  /* Number the dossier sections by actual render order via a CSS counter, so the
     sequence stays contiguous (01,02,03…) even when a section is conditionally
     absent. Never hardcode per-id "01"/"02" literals (they desync on conditionals). */
  :global(.discovery-dossier) {
    counter-reset: dossier-section;
  }
  :global(.discovery-dossier .section-container.expandable) {
    counter-increment: dossier-section;
  }
  :global(.discovery-dossier .section-container.expandable .section-header-title::before) {
    content: counter(dossier-section, decimal-leading-zero);
    margin-right: 0.5rem;
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 800;
    letter-spacing: 0.04em;
  }

  :global(.discovery-dossier .section-container.expandable .section-body-inner) {
    border-color: color-mix(in srgb, var(--color-border-emphasis) 34%, transparent);
    border-radius: 0.875rem;
    background:
      color-mix(in srgb, var(--color-bg-elevated) 88%, var(--color-bg-surface));
  }

  :global(.discovery-dossier .section-container.expandable .section-content) {
    padding: 0.9rem 0.96rem 1rem !important;
  }

  :global(.job-selection-header) {
    margin-bottom: 0;
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

  :global(.job-selection-header h1) {
    max-width: 34ch;
    font-size: clamp(1.25rem, 1.72vw, 1.5rem);
    line-height: 1.13;
    letter-spacing: -0.01em;
  }

  :global(.job-selection-header p) {
    max-width: 44rem;
    margin-top: 0.38rem;
    font-size: 0.9375rem;
  }

  :global(.job-selection-header .page-header-title-row > div:first-child) {
    padding: 0.42rem;
    border-radius: 0.75rem;
  }

  :global(.job-selection-header .page-header-title-row svg) {
    width: 1.25rem;
    height: 1.25rem;
  }

  @media (max-width: 1279px) {
    .job-page-content {
      padding: 1rem;
      width: 100%;
    }
  }

  @media (max-width: 760px) {
    .discovery-dossier {
      padding: 0.44rem;
      border-radius: 0.875rem;
    }

    .dossier-header {
      grid-template-columns: minmax(0, 1fr);
      padding: 0.7rem 0.72rem 0.78rem;
    }

    .dossier-ledger {
      grid-template-columns: repeat(3, minmax(0, 1fr));
      min-width: 0;
      width: 100%;
    }

    :global(.discovery-dossier .section-container.expandable .expandable-trigger) {
      padding-inline: 0.34rem;
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
