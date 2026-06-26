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
  import CommunitySourcesSection from "$lib/components/preview/CommunitySourcesSection.svelte";
  import PreviewSolutionSelector from "$lib/components/preview/PreviewSolutionSelector.svelte";
  import ResearchProgressScreen from "$lib/components/preview/ResearchProgressScreen.svelte";

  import DeepResearchCTABlock from "$lib/components/preview/DeepResearchCTABlock.svelte";
  import SEOKeywordsPreview from "$lib/components/preview/SEOKeywordsPreview.svelte";
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

  // Placeholder data for locked sections — use short niche name, not full description
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
  });

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

  // All pain points sorted by severity
  const topPainPoints = $derived(
    (previewReport?.detailed_pain_points ?? [])
      .slice()
      .sort((a, b) => b.severity_score - a.severity_score)
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
  <title>{job ? `${titleCase(nicheName) || job.niche} — ${getStatusLabel(job.status)}` : 'Job'} - NicheIQ</title>
</svelte:head>

<div class="job-page-shell" class:has-sticky-bar={isSelectionPhase && showStickyBar}>
  {#if job && !isGenerating}
    <PhaseNav jobStatus={job.status} entryMode={job.entryMode} />
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
      <div class="job-hero-grid">
        <div class="job-hero-main">
          <PageHeader
            icon={Telescope}
            breadcrumbItems={[{ label: 'Dashboard', href: '/dashboard' }]}
            breadcrumbCurrent={titleCase(nicheName) || 'Research'}
            title={titleCase(nicheName) || 'Research Progress'}
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
                <Badge variant={getStatusVariant(isRegenQueued ? 'REGENERATING' : job.status)}>
                  {#if ['RUNNING', 'RUNNING_PHASE2', 'REGENERATING'].includes(job.status) || isRegenQueued}
                    <Loader2 class="w-3.5 h-3.5 animate-spin" />
                  {/if}
                  {getStatusLabel(isRegenQueued ? 'REGENERATING' : job.status)}
                </Badge>
              </div>
            {/snippet}
          </PageHeader>
        </div>
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
      </div>

      <!-- ═══ PROGRESS STEPPER ═══ -->
      <ProgressStepper
        currentStep={stepperStep}
        {discussionCount}
        painPointCount={previewPainPointCount}
        solutionCount={displaySolutions.length}
      />

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

      <!-- ═══ DASHBOARD SECTIONS ═══ -->
      {#if !isGeneratingP1}

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

        <!-- Opportunities (Selection) — promoted above supporting evidence -->
        {#if displaySolutions.length > 0}
          <div class={isSelectionPhase ? 'opportunities-zone' : ''}>
          {#if isSelectionPhase}
            <div class="action-banner" id="solution-selector" bind:this={ctaBannerRef}>
              <div class="action-banner-badge">Action Required</div>
              <p class="action-banner-text">
                Select up to 3 solutions to compare. Deep Research will validate the most promising one.
                <strong>{ADDITIONAL_LOCKED_SECTIONS.length + LOCKED_PREVIEW_SECTIONS.length} sections</strong> unlock for {page.data.stageCosts?.deep_research ?? 15} credits.
              </p>
            </div>
          {/if}
          <ExpandableSection
            title="Opportunities"
            count={displaySolutions.length}
            countSuffix="opportunities"
            variant={isSelectionPhase ? "default" : "accent"}
            defaultOpen={discoveryOpen}
            resetKey={sectionResetKey}
            id="opportunities"
          >
            {#if isSelectionPhase}
              <PreviewSolutionSelector
                jobId={jobId ?? ''}
                solutions={displaySolutions}
                coverageNotes={previewReport?.data_quality_summary?.quality_caveats ?? []}
                primaryAudience={previewReport?.niche_context?.resolved_primary_audience ?? null}
                audienceLabel={previewReport?.niche_context?.user_target_audience ?? null}
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
          </div>
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
            title="Pain Points"
            count={previewPainPointCount}
            countSuffix="clusters"
            variant="success"
            defaultOpen={discoveryOpen}
            resetKey={sectionResetKey}
            id="pain-points"
          >
            <p class="section-intro">What are people struggling with? Each pain point scored by how much it blocks real work (severity) and its commercial-intent signal.</p>
            {#each topPainPoints as pp, i}
              <PainPointSummaryCard painPoint={pp} rank={i + 1} isTop={i === 0} onViewOpportunity={scrollToSolutions} />
            {/each}

          </ExpandableSection>
        {/if}

        <!-- Audience — rendered at full width without ExpandableSection; the
             AudienceSection component owns its own section chrome + hero strip. -->
        {#if previewReport?.audience_mapping}
          <AudienceSection data={previewReport.audience_mapping} />
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

        <!-- ═══ DEEP RESEARCH PREVIEW SECTIONS ═══ -->
        {#if !isCompleted}
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

          <!-- SEO Keywords preview — editorial hairline insert between capped cards -->
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
    {/if}

    {#if isSelectionPhase}
      <div class="sticky-bar-spacer" aria-hidden="true"></div>
    {/if}
  </main>
</div>

<!-- ═══ STICKY BAR (selection phase only) ═══ -->
{#if job && isSelectionPhase && showStickyBar}
  <div class="sticky-bar" role="region" aria-label="Selection summary">
    <div class="sticky-bar-inner" role="status" aria-live="polite">
      <div class="sticky-bar-context">
        <span class="sticky-bar-heading">Ready to go deeper?</span>
        {#if stickySelectionCount > 0}
          <div class="sticky-bar-pills">
            {#each stickySelectionNames.slice(0, 3) as name}
              <span class="sticky-bar-pill">{name.length > 30 ? name.slice(0, 28) + '...' : name}</span>
            {/each}
          </div>
        {:else}
          <span class="sticky-bar-sub">Market Sizing, SEO, Competitors & {ADDITIONAL_LOCKED_SECTIONS.length} more · {page.data.stageCosts?.deep_research ?? 15} credits · one-time per niche</span>
        {/if}
      </div>
      {#if stickySelectionCount > 0}
        <button
          class="btn-primary btn-sm sticky-bar-btn"
          onclick={() => { validateTrigger++; }}
        >
          {#if !stickyCanAfford}
            Add credits to start
          {:else}
            Start Deep Research · {page.data.stageCosts?.deep_research ?? 15} credits <ArrowRight class="w-3.5 h-3.5" aria-hidden="true" />
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
    transition: color 150ms ease, border-color 150ms ease, background-color 150ms ease;
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


  /* ═══ Opportunities zone (warm wrapper during selection) ═══ */
  .opportunities-zone {
    margin-bottom: var(--space-4);
  }

  /* ═══ Action banner (opportunities callout) ═══ */
  .action-banner {
    padding: var(--space-5) var(--space-6);
    margin-bottom: var(--space-3);
    background: rgba(234, 88, 12, 0.10);
    border: 1px solid rgba(234, 88, 12, 0.18);
    border-radius: var(--radius-lg, 0.75rem);
  }

  .action-banner-badge {
    display: inline-block;
    background: var(--color-accent);
    color: white;
    font-family: var(--font-display);
    font-size: 0.6875rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    padding: var(--space-1) var(--space-3);
    border-radius: 0.25rem;
    margin-bottom: var(--space-3);
  }

  .action-banner-text {
    font-size: 0.875rem;
    color: var(--color-text-secondary);
    line-height: 1.6;
  }

  .action-banner-text strong {
    color: var(--color-text-primary);
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

  .sticky-bar-spacer {
    height: 5.5rem;
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

    .sticky-bar-spacer {
      height: 8rem;
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
