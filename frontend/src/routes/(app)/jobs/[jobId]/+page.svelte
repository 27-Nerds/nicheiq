<script lang="ts">
  import { untrack } from "svelte";
  import { page } from "$app/state";
  import { invalidateAll } from "$app/navigation";
  import {
    subscribeToProgress,
    isTerminalStatus,
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
    Clock,
    CheckCircle,
    X,
    ArrowRight,
    Telescope,
    RotateCw,
    Package,
    Share2,
    BarChart3,
  } from "lucide-svelte";
  import { showNewResearchModal } from "$lib/stores/newResearchModal.svelte";
  import { creditTopUp } from "$lib/stores/creditTopUp.svelte";
  import type { Job, StageProgress, SolutionPreview, ReportSummary } from "$lib/types/job";
  import Button from "$lib/components/ui/Button.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";
  import SelectedSolutionsSummary from "$lib/components/SelectedSolutionsSummary.svelte";
  import DeliverableRow from "$lib/components/job/DeliverableRow.svelte";

  // Preview / Dashboard components
  import PhaseNav from "$lib/components/nav/PhaseNav.svelte";
  import ExpandableSection from "$lib/components/ui/ExpandableSection.svelte";
  import PreviewOverview from "$lib/components/preview/PreviewOverview.svelte";
  import ProgressStepper from "$lib/components/preview/ProgressStepper.svelte";
  import PainPointSummaryCard from "$lib/components/preview/PainPointSummaryCard.svelte";
  import CommunitySourcesSection from "$lib/components/preview/CommunitySourcesSection.svelte";
  import PreviewSolutionSelector from "$lib/components/preview/PreviewSolutionSelector.svelte";
  import GenerationSlideshow from "$lib/components/preview/GenerationSlideshow.svelte";
  import LockedSection from "$lib/components/preview/LockedSection.svelte";
  import DeepResearchCTABlock from "$lib/components/preview/DeepResearchCTABlock.svelte";
  import MarketSnapshot from "$lib/components/preview/MarketSnapshot.svelte";
  import DiscoveryEvidence from "$lib/components/discovery/DiscoveryEvidence.svelte";
  import AudienceSection from "$lib/components/sections/AudienceSection.svelte";
  import UnifiedHero from "$lib/components/sections/UnifiedHero.svelte";
  import Competitors from "$lib/components/sections/Competitors.svelte";
  import { LOCKED_PREVIEW_SECTIONS, ADDITIONAL_LOCKED_SECTIONS } from "$lib/types/previewReport";
  import {
    placeholderExecutiveDashboard,
    placeholderCompetitors,
  } from "$lib/data/previewPlaceholders";
  import { PHASES, PARALLEL_STAGE_GROUPS } from "$lib/components/job/phaseConfig";
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
            if (!localSolutions || sseData.solutionIdeas.length !== localSolutions.length) {
              clientSolutions = sseData.solutionIdeas as SolutionPreview[];
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
    catch { /* graceful fallback — old jobs won't have this asset */ }
    finally { discoveryLoading = false; }
  }

  let previewReportLoading = $state(false);
  async function loadPreviewReport(id: string) {
    if (previewReportLoading) return;
    previewReportLoading = true;
    try { clientPreviewReport = await getPreviewReport(id); }
    catch { /* graceful fallback — old jobs won't have preview report */ }
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
      case "AWAITING_SELECTION": return "Awaiting Selection";
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
    document.getElementById('solution-selector')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function formatDuration(seconds: number | null): string {
    if (!seconds) return "";
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const totalSeconds = Math.round(seconds);
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${mins}m ${secs}s`;
  }

  // Process stages for display (combine parallel stages)
  function processStagesForDisplay(stages: StageProgress[], jobStatus: string): StageProgress[] {
    const hiddenStages = new Set<number>();
    for (const group of Object.values(PARALLEL_STAGE_GROUPS)) {
      group.hide.forEach((s) => hiddenStages.add(s));
    }
    return stages
      .filter((stage) => !hiddenStages.has(stage.stageNumber))
      .map((stage) => {
        const group = PARALLEL_STAGE_GROUPS[stage.stageNumber];
        let processed = group ? { ...stage, stageName: group.combinedName } : stage;
        if ((jobStatus === "FAILED" || jobStatus === "CANCELLED") && processed.status === "RUNNING") {
          processed = { ...processed, status: "FAILED" };
        }
        // After failed regeneration, job reverts to AWAITING_SELECTION but stage 5 may still be RUNNING in DB
        if (jobStatus === "AWAITING_SELECTION" && processed.status === "RUNNING") {
          processed = { ...processed, status: "COMPLETED" };
        }
        return processed;
      });
  }

  const displayStages = $derived(
    job ? processStagesForDisplay(job.progress ?? [], job.status) : [],
  );

  // Adjusted counts
  const adjustedStagesCompleted = $derived.by(() => {
    if (!job) return 0;
    const hiddenStageNumbers = Object.values(PARALLEL_STAGE_GROUPS).flatMap((g) => g.hide);
    const hiddenCompleted = (job.progress ?? []).filter(
      (s) => hiddenStageNumbers.includes(s.stageNumber) && s.status === "COMPLETED",
    ).length;
    return job.stagesCompleted - hiddenCompleted;
  });

  const adjustedTotalStages = $derived.by(() => {
    if (!job) return 0;
    const hiddenCount = Object.values(PARALLEL_STAGE_GROUPS).flatMap((g) => g.hide).length;
    return job.totalStages - hiddenCount;
  });

  // Build artifact maps from stage progress
  const stageArtifacts = $derived.by(() => {
    const map: Record<number, Record<string, any>> = {};
    for (const stage of job?.progress ?? []) {
      if (stage.artifact && typeof stage.artifact === 'object') {
        map[stage.stageNumber] = stage.artifact as Record<string, any>;
      }
    }
    // When the final report is available, use its definitive SEO metrics
    // (Stage 6 only validates ~10 seed keywords; the full report has all tiered keywords)
    if (reportSummary && map[6]) {
      map[6] = {
        ...map[6],
        total_volume: reportSummary.total_search_volume ?? map[6].total_volume,
        validated_keywords: reportSummary.total_keywords ?? map[6].validated_keywords,
      };
    }
    return map;
  });

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

  // Section open state driven by lifecycle (passes to ExpandableSection defaultOpen)
  const discoveryOpen = $derived(isSelectionPhase);
  const deepResearchOpen = $derived(job?.status === 'COMPLETED');

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

  const discussionCount = $derived(
    (previewReport?.research_metadata?.filtering_stats as Record<string, number>)?.reddit_urls_relevant ??
    previewReport?.research_metadata?.reddit_posts_analyzed ?? 0
  );

  const previewPainPointCount = $derived(
    previewReport?.pain_point_analytics?.total_pain_points ??
    previewReport?.detailed_pain_points?.length ?? 0
  );

  const segmentCount = $derived(
    previewReport?.audience_mapping?.audience_segments?.length ?? 0
  );

  // Placeholder data for locked sections
  const niche = $derived(previewReport?.niche ?? job?.niche ?? '');
  const placeholderExec = $derived(placeholderExecutiveDashboard(niche));
  const placeholderComp = $derived(placeholderCompetitors(niche));

  // Sticky bar state
  let ctaBannerRef = $state<HTMLElement | null>(null);
  let showStickyBar = $state(false);
  let stickySelectionCount = $state(0);
  let stickyCanAfford = $state(true);
  let stickySelectionNames = $state<string[]>([]);
  let validateTrigger = $state(0);

  $effect(() => {
    if (!ctaBannerRef) return;
    const observer = new IntersectionObserver(
      ([entry]) => { showStickyBar = !entry.isIntersecting; },
      { threshold: 0 },
    );
    observer.observe(ctaBannerRef);
    return () => observer.disconnect();
  });

  // Top pain points for summary cards
  const topPainPoints = $derived(
    (previewReport?.detailed_pain_points ?? [])
      .slice()
      .sort((a, b) => b.severity_score - a.severity_score)
      .slice(0, 5)
  );

  let showFullAnalysis = $state(false);

  // Display current stage name (with parallel group handling)
  const displayCurrentStageName = $derived(
    job
      ? (job.currentStage === 3 || job.currentStage === 4
          ? PARALLEL_STAGE_GROUPS[3].combinedName
          : job.currentStageName || "Initializing...")
      : ""
  );

  // Report-ready reveal: trigger once when job transitions to COMPLETED
  const isCompleted = $derived(job?.status === 'COMPLETED');

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
  <title>{job ? `${nicheName || job.niche} — ${getStatusLabel(job.status)}` : 'Job'} - NicheIQ</title>
</svelte:head>

<div class="job-page-shell">
  {#if job}
    <PhaseNav jobStatus={job.status} />
  {/if}
  <main class="job-page-content">
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
        <Button onclick={() => (showNewResearchModal.open = true)} label="Start New Research" class="mt-6 btn-primary inline-block" />
      </div>
    {:else if job}
      <!-- ═══ HEADER ═══ -->
      <PageHeader
        icon={Telescope}
        breadcrumbItems={[{ label: 'Dashboard', href: '/dashboard' }]}
        breadcrumbCurrent={nicheName || 'Research'}
        title={nicheName || 'Research Progress'}
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
            {#if isGeneratingP1 && !isRegenQueued}
              <SubmitButton onclick={cancelJob} loading={cancelling} loadingText="Cancelling..." icon={X} label="Cancel" class="btn-secondary btn-sm whitespace-nowrap text-error border-error/30 hover:bg-error/10 hover:border-error disabled:opacity-50 disabled:cursor-not-allowed" />
            {/if}
            {#if isCompleted && reportAsset}
              <Button href="/jobs/{job.id}/report" icon={REPORT_ICON} label="View Report" class="btn-primary btn-sm" />
            {/if}
            <Badge variant={getStatusVariant(isRegenQueued ? 'REGENERATING' : job.status)}>
              {#if ['RUNNING', 'RUNNING_PHASE2', 'REGENERATING'].includes(job.status) || isRegenQueued}
                <Loader2 class="w-3.5 h-3.5 animate-spin" />
              {/if}
              {getStatusLabel(isRegenQueued ? 'REGENERATING' : job.status)}
            </Badge>
          </div>
        {/snippet}
      </PageHeader>

      <!-- ═══ PROGRESS STEPPER ═══ -->
      <ProgressStepper
        currentStep={stepperStep}
        {discussionCount}
        painPointCount={previewPainPointCount}
        solutionCount={displaySolutions.length}
      />

      <!-- ═══ QUEUE POSITION ═══ -->
      {#if (job.status === 'QUEUED' || job.status === 'PENDING') && !isRegenQueued}
        <div class="card p-6 mb-6 bg-warning/5 border-warning/20">
          <div class="flex items-center gap-4">
            <div class="p-3 rounded-full bg-warning/10 border border-warning/20">
              <Clock class="w-6 h-6 text-warning" />
            </div>
            <div>
              <p class="font-semibold text-text-primary text-lg">
                {#if job.queuePosition === 1}
                  You're next!
                {:else if job.queuePosition && job.aheadCount}
                  {job.aheadCount} {job.aheadCount === 1 ? 'report' : 'reports'} ahead of you
                {:else}
                  Waiting in queue...
                {/if}
              </p>
              {#if job.queuePosition}
                <p class="text-sm text-text-muted mt-0.5">
                  Position <span class="tabular-nums">{job.queuePosition}</span> of <span class="tabular-nums">{job.totalQueued}</span> in queue
                </p>
              {/if}
            </div>
          </div>
        </div>
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
              <button onclick={() => (showNewResearchModal.open = true)} class="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-accent hover:text-accent-hover transition-colors">
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
              <div class="mt-4 flex items-center gap-2">
                <CheckCircle class="w-4 h-4 text-success" />
                <span class="text-sm text-success">Credits refunded automatically</span>
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

      <!-- ═══ GENERATION SLIDESHOW (Phase 1 or Phase 2) ═══ -->
      {#if isGeneratingP1 && job.status === 'RUNNING'}
        <div class="generation-area">
          <div class="progress-bar-track">
            <div class="progress-bar-fill" style:width="{job.progressPercent ?? 0}%"></div>
          </div>
          <p class="progress-stage">
            Stage {adjustedStagesCompleted} of {adjustedTotalStages}{#if displayCurrentStageName}: {displayCurrentStageName}{/if}
          </p>
          <GenerationSlideshow currentStage={job.currentStage} phase="discovery" />
        </div>
      {:else if isGeneratingP2}
        <div class="generation-area">
          {#if showSelectedSummary}
            <div class="mb-4">
              <SelectedSolutionsSummary
                selectedNames={job.selectedSolutions ?? []}
                solutionIdeas={job.solutionIdeas ?? []}
                primaryWinner={job.selectedSolution}
                status={job.status}
              />
            </div>
          {/if}
          <div class="progress-bar-track">
            <div class="progress-bar-fill" style:width="{job.progressPercent ?? 0}%"></div>
          </div>
          <p class="progress-stage">
            Stage {adjustedStagesCompleted} of {adjustedTotalStages}{#if displayCurrentStageName}: {displayCurrentStageName}{/if}
          </p>
          <GenerationSlideshow currentStage={job.currentStage} phase="deep_research" />
        </div>
      {/if}

      <!-- ═══ DASHBOARD SECTIONS ═══ -->
      {#if !isGeneratingP1 || job.status !== 'RUNNING'}

        <!-- Overview -->
        {#if previewReport}
          <ExpandableSection title="Overview" variant="success" defaultOpen={true} resetKey={sectionResetKey} id="overview">
            <PreviewOverview
              nicheName={nicheName}
              nicheDescription={previewReport.niche_context?.niche_description}
              {discussionCount}
              painPointCount={previewPainPointCount}
              solutionCount={displaySolutions.length}
              {segmentCount}
            />
          </ExpandableSection>
        {/if}

        <!-- Market Snapshot -->
        {#if discoveryData?.discussion_trend?.length}
          <ExpandableSection
            title="Market Snapshot"
            icon={BarChart3}
            defaultOpen={true}
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
            title="Pain Point Analysis"
            count={previewPainPointCount}
            countSuffix="clusters"
            variant="success"
            defaultOpen={discoveryOpen}
            resetKey={sectionResetKey}
            id="pain-points"
          >
            <p class="section-intro">What are people struggling with? Each pain point scored by frequency, emotional intensity, and willingness to pay.</p>
            {#each topPainPoints as pp, i}
              <PainPointSummaryCard painPoint={pp} rank={i + 1} isTop={i === 0} onViewOpportunity={scrollToSolutions} />
            {/each}

            {#if previewReport.pain_point_analytics}
              <button class="show-full-toggle" onclick={() => (showFullAnalysis = !showFullAnalysis)}>
                {showFullAnalysis ? 'Hide' : 'Show'} full analysis ({previewPainPointCount} clusters)
              </button>
              {#if showFullAnalysis}
                <div class="mt-4">
                  <!-- PainAnalysis would go here — import when needed to avoid loading 1,281 lines upfront -->
                </div>
              {/if}
            {/if}
          </ExpandableSection>
        {/if}

        <!-- Audience -->
        {#if previewReport?.audience_mapping}
          <ExpandableSection
            title="Audience Analysis"
            count={segmentCount}
            countSuffix="segments"
            variant="success"
            defaultOpen={false}
            resetKey={sectionResetKey}
            id="audience"
          >
            <p class="section-intro">Who is affected? Audience segments identified from community discussions.</p>
            <AudienceSection data={previewReport.audience_mapping} />
          </ExpandableSection>
        {/if}

        <!-- Community & Sources -->
        {#if discoveryData || previewReport?.evidence_appendix}
          <ExpandableSection
            title="Community & Sources"
            count={discoveryData?.subreddit_names?.length ?? 0}
            countSuffix="sources"
            variant="success"
            defaultOpen={false}
            resetKey={sectionResetKey}
            id="community"
          >
            <p class="section-intro">Where do these conversations happen? Source communities and top evidence threads.</p>
            <CommunitySourcesSection
              subredditNames={discoveryData?.subreddit_names}
              communityHubs={previewReport?.audience_mapping?.community_hubs}
              topThreads={previewReport?.evidence_appendix?.top_reddit_threads}
              postsAnalyzed={previewReport?.research_metadata?.reddit_posts_analyzed}
            />

            {#if discoveryData?.social_posts_sample?.length}
              <DiscoveryEvidence data={discoveryData} />
            {/if}

            {#if discoveryData?.methodology}
              <p class="methodology-note">
                Based on {discoveryData.methodology.urls_searched.toLocaleString()} URLs scanned &middot;
                {discoveryData.methodology.urls_relevant} relevant ({discoveryData.methodology.filtering_rate}%) &middot;
                {discoveryData.methodology.quality_tier} quality
              </p>
            {/if}
          </ExpandableSection>
        {/if}

        <!-- Opportunities (Selection) -->
        {#if displaySolutions.length > 0}
          <ExpandableSection
            title="Opportunities"
            count={displaySolutions.length}
            countSuffix="ideas"
            variant="accent"
            defaultOpen={discoveryOpen}
            resetKey={sectionResetKey}
            id="opportunities"
          >
            {#if isSelectionPhase}
              <div class="action-zone" id="solution-selector" bind:this={ctaBannerRef}>
                <div class="action-zone-badge">Action Required</div>
                <p class="action-zone-text">
                  Select up to 3 ideas to compare. Deep Research will validate the most promising one.
                  <strong>{ADDITIONAL_LOCKED_SECTIONS.length + LOCKED_PREVIEW_SECTIONS.length} sections</strong> unlock with your selection.
                </p>
              </div>

              <PreviewSolutionSelector
                jobId={jobId ?? ''}
                solutions={displaySolutions}
                creditBalance={page.data.creditBalance ?? 0}
                stageCosts={page.data.stageCosts ?? { discovery: 5, deep_research: 15, landing_page: 5, regenerate_ideas: 2 }}
                canRegenerate={job.canRegenerate ?? false}
                isRegenerating={job.status === 'REGENERATING' || isRegenQueued}
                selectedSolutions={job.selectedSolutions ?? undefined}
                {solutionVotes}
                onComplete={handleSelectionComplete}
                onSelectionComplete={handleSelectionComplete}
                onRegenerateStart={() => { clientJob = { ...job!, status: 'QUEUED' }; }}
                onSelectionChange={(info) => {
                  stickySelectionCount = info.count;
                  stickyCanAfford = info.canAfford;
                  stickySelectionNames = info.names;
                }}
                bind:externalValidate={validateTrigger}
              />
            {:else if showSelectedSummary && !isGeneratingP2}
              <SelectedSolutionsSummary
                selectedNames={job.selectedSolutions ?? []}
                solutionIdeas={job.solutionIdeas ?? []}
                primaryWinner={job.selectedSolution}
                status={job.status}
              />
            {/if}
          </ExpandableSection>
        {/if}

        <!-- ═══ DEEP RESEARCH CTA ═══ -->
        {#if isSelectionPhase}
          <DeepResearchCTABlock
            creditCost={page.data.stageCosts?.deep_research ?? 15}
            onUnlock={scrollToSolutions}
          />
        {/if}

        <!-- ═══ LOCKED DEEP RESEARCH SECTIONS ═══ -->
        {#if !isCompleted}
          <!-- Keep 2 high-impact blurred previews for Zeigarnik curiosity -->
          {#each LOCKED_PREVIEW_SECTIONS.filter(c => c.id === 'unified-hero' || c.id === 'competitors') as config (config.id)}
            <section id={config.id} class="locked-section-wrapper">
              <LockedSection
                sectionNumber={config.sectionNumber}
                title={config.title}
                teaser={isGeneratingP2
                  ? `Generating... stage ${adjustedStagesCompleted}/${adjustedTotalStages}`
                  : config.teaser}
              >
                {#if config.id === 'unified-hero'}
                  <UnifiedHero report={placeholderExec} nicheName={niche} nicheDescription={`Analysis of the ${niche} market`} funnelStats={{ scanned: 120, relevant: 79, analyzed: 50, problems: 4 }} />
                {:else if config.id === 'competitors'}
                  <Competitors profiles={placeholderComp.profiles} analysis={placeholderComp.analysis} analytics={placeholderComp.analytics} selectedSolutionName={`${niche} Opportunity Analyzer`} />
                {/if}
              </LockedSection>
            </section>
          {/each}

          <!-- Compact pill card for remaining locked sections -->
          <div class="unlock-card">
            <h3 class="unlock-title">
              {LOCKED_PREVIEW_SECTIONS.filter(c => c.id !== 'unified-hero' && c.id !== 'competitors').length + ADDITIONAL_LOCKED_SECTIONS.length} more sections unlock with Deep Research
            </h3>
            <div class="unlock-pills">
              {#each LOCKED_PREVIEW_SECTIONS.filter(c => c.id !== 'unified-hero' && c.id !== 'competitors') as config}
                <span class="unlock-pill">{config.title}</span>
              {/each}
              {#each ADDITIONAL_LOCKED_SECTIONS as title}
                <span class="unlock-pill unlock-pill--extra">{title}</span>
              {/each}
            </div>
          </div>
        {:else if reportSummary}
          <!-- ═══ COMPLETED: Report summary cards ═══ -->
          <div class="report-summary-card">
            <div class="report-summary-header">
              <h2 class="report-summary-title">Your Report is Ready</h2>
              <Button href="/jobs/{job.id}/report" icon={REPORT_ICON} label="View Full Report" class="btn-primary btn-sm" />
            </div>
            <div class="report-summary-metrics">
              {#if reportSummary.opportunity_score != null}
                <div class="report-metric">
                  <span class="report-metric-value">{reportSummary.opportunity_score > 1 ? reportSummary.opportunity_score : Math.round(reportSummary.opportunity_score * 100)}</span>
                  <span class="report-metric-label">Score</span>
                </div>
              {/if}
              {#if reportSummary.verdict}
                <div class="report-metric">
                  <span class="report-metric-value report-metric-value--{reportSummary.verdict.toLowerCase() === 'go' ? 'success' : 'warning'}">{reportSummary.verdict}</span>
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

      <!-- ═══ META ═══ -->
      <div class="mt-6 p-4 rounded-lg bg-bg-surface border border-border">
        <div class="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-sm text-text-muted">
          <span class="font-mono text-xs">ID: {job.id.substring(0, 8)}...</span>
          {#if job.startedAt}
            <span>Started: {new Date(job.startedAt).toLocaleString()}</span>
          {/if}
          {#if job.completedAt}
            <span>Completed: {new Date(job.completedAt).toLocaleString()}</span>
          {/if}
        </div>
      </div>
    {/if}
  </main>
</div>

<!-- ═══ STICKY BAR (selection phase only) ═══ -->
{#if job && isSelectionPhase && showStickyBar}
  <div class="sticky-bar">
    <div class="sticky-bar-inner">
      <div class="sticky-bar-context">
        <span class="sticky-bar-heading">Ready to go deeper?</span>
        {#if stickySelectionCount > 0}
          <div class="sticky-bar-pills">
            {#each stickySelectionNames.slice(0, 3) as name}
              <span class="sticky-bar-pill">{name.length > 30 ? name.slice(0, 28) + '...' : name}</span>
            {/each}
          </div>
        {:else}
          <span class="sticky-bar-sub">Market Sizing, SEO, Competitors & {ADDITIONAL_LOCKED_SECTIONS.length} more sections</span>
        {/if}
      </div>
      {#if stickySelectionCount > 0}
        <button
          class="btn-primary btn-sm sticky-bar-btn"
          onclick={() => { validateTrigger++; }}
        >
          {#if !stickyCanAfford}
            Add credits
          {:else}
            Start Deep Research <ArrowRight class="w-3.5 h-3.5" />
          {/if}
        </button>
      {:else}
        <button
          class="btn-primary btn-sm sticky-bar-btn"
          onclick={scrollToSolutions}
        >
          Select a solution <ArrowRight class="w-3.5 h-3.5" />
        </button>
      {/if}
    </div>
  </div>
{/if}

{#if jobId}
  <ShareDiscoveryModal bind:open={discoveryShareOpen} jobId={jobId} />
{/if}

<style>
  /* ═══ Page shell: sidebar + content ═══ */
  .job-page-shell {
    display: flex;
    min-height: 100vh;
  }

  .job-page-content {
    width: min(56rem, 100%);
    margin: 0 auto;
    min-width: 0;
    padding: 2rem 2.5rem 5rem;
  }

  @media (max-width: 1279px) {
    .job-page-content {
      padding: 1rem;
      width: 100%;
    }
  }

  /* ═══ Generation area ═══ */
  .generation-area {
    padding: var(--space-8, 2rem);
    margin-bottom: 1.5rem;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg, 0.75rem);
    text-align: center;
  }

  .progress-bar-track {
    height: 6px;
    background: var(--color-bg-surface);
    border-radius: 3px;
    overflow: hidden;
    margin-bottom: 0.75rem;
  }

  .progress-bar-fill {
    height: 100%;
    background: var(--color-accent);
    border-radius: 3px;
    transition: width 100ms linear;
  }

  .progress-stage {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: var(--color-text-muted);
    font-variant-numeric: tabular-nums;
    margin-bottom: 1rem;
  }

  /* ═══ Section intro ═══ */
  .section-intro {
    font-size: 0.875rem;
    color: var(--color-text-secondary);
    line-height: 1.6;
    margin-bottom: 1rem;
  }

  /* ═══ Methodology footnote ═══ */
  .methodology-note {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    color: var(--color-text-muted);
    letter-spacing: 0.02em;
    margin-top: var(--space-4);
    padding-top: var(--space-3);
    border-top: 1px solid var(--color-border);
  }

  /* ═══ Show full analysis toggle ═══ */
  .show-full-toggle {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    margin-top: 1rem;
    padding: 0.5rem 1rem;
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--color-text-secondary);
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md, 0.5rem);
    cursor: pointer;
    transition: background-color 0.15s ease, border-color 0.15s ease;
  }

  .show-full-toggle:hover {
    background: var(--color-bg-elevated);
    border-color: var(--color-border-emphasis, var(--color-border));
  }

  /* ═══ Action zone (opportunities) ═══ */
  .action-zone {
    position: relative;
    padding: 1rem 1.25rem;
    padding-top: 1.25rem;
    margin-bottom: 1.25rem;
    background: var(--color-accent-subtle);
    border: 1.5px solid var(--color-border-accent);
    border-radius: var(--radius-lg, 0.75rem);
  }

  .action-zone-badge {
    position: absolute;
    top: -1px;
    left: 1rem;
    transform: translateY(-50%);
    background: var(--color-accent);
    color: white;
    font-family: var(--font-display);
    font-size: 0.6875rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    padding: 0.25rem 0.75rem;
    border-radius: 0.25rem;
  }

  .action-zone-text {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    line-height: 1.5;
  }

  .action-zone-text strong {
    color: var(--color-text-primary);
  }

  /* ═══ Unlock card (compact pill list) ═══ */
  .unlock-card {
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg, 0.75rem);
  }

  .unlock-title {
    font-family: var(--font-display);
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--color-text-secondary);
    margin: 0 0 0.75rem;
  }

  .unlock-pills {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
  }

  .unlock-pill {
    font-size: 0.75rem;
    font-weight: 500;
    padding: 0.25rem 0.625rem;
    background: var(--color-accent-subtle);
    border: 1px solid var(--color-border-accent);
    border-radius: 9999px;
    color: var(--color-accent);
    white-space: nowrap;
  }

  .unlock-pill--extra {
    background: var(--color-bg-surface);
    border-color: var(--color-border);
    color: var(--color-text-muted);
  }

  @media (max-width: 639px) {
    .unlock-pills {
      max-height: 4.5rem;
      overflow: hidden;
      position: relative;
    }
  }

  /* ═══ Locked section wrapper ═══ */
  .locked-section-wrapper {
    padding-bottom: 0.75rem;
  }

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

  .report-metric-label {
    font-size: 0.6875rem;
    font-weight: 500;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  /* ═══ Sticky bar ═══ */
  .sticky-bar {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: color-mix(in srgb, var(--color-bg-base) 92%, transparent);
    backdrop-filter: blur(12px);
    border-top: 2px solid var(--color-accent);
    z-index: var(--z-dropdown, 40);
    min-height: 56px;
    display: flex;
    align-items: center;
    justify-content: center;
    animation: stickyBarEnter 200ms ease-out;
  }

  @keyframes stickyBarEnter {
    from { transform: translateY(100%); opacity: 0; }
    to { transform: translateY(0); opacity: 1; }
  }

  .sticky-bar-inner {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.625rem 1.25rem;
    max-width: 1200px;
    width: 100%;
    justify-content: space-between;
  }

  .sticky-bar-context {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    min-width: 0;
  }

  .sticky-bar-heading {
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .sticky-bar-sub {
    font-size: 0.75rem;
    color: var(--color-text-muted);
  }

  .sticky-bar-pills {
    display: flex;
    gap: 0.375rem;
    flex-wrap: wrap;
  }

  .sticky-bar-pill {
    font-size: 0.6875rem;
    font-weight: 500;
    padding: 0.1875rem 0.5rem;
    background: var(--color-accent-subtle);
    border: 1px solid var(--color-border-accent);
    border-radius: 9999px;
    color: var(--color-accent);
    max-width: 12rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .sticky-bar-btn {
    min-height: 40px;
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .sticky-bar-btn:active {
    transform: scale(0.97);
  }

  /* gate-locked and stage-list removed — no longer used in unified dashboard */

  /* ═══ Responsive ═══ */
  @media (max-width: 639px) {
    .sticky-bar-inner {
      flex-direction: column;
      gap: 0.5rem;
      text-align: center;
    }

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

  /* extras-card--locked removed — extras only shown when complete */

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
