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
  } from "lucide-svelte";
  import { showNewResearchModal } from "$lib/stores/newResearchModal.svelte";
  import type { Job, StageProgress, SolutionPreview, ReportSummary } from "$lib/types/job";
  import ProgressRing from "$lib/components/ui/ProgressRing.svelte";
  import Button from "$lib/components/ui/Button.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";
  import SolutionSelectionView from "$lib/components/SolutionSelectionView.svelte";
  import SelectedSolutionsSummary from "$lib/components/SelectedSolutionsSummary.svelte";
  import PhaseResultsCard from "$lib/components/PhaseResultsCard.svelte";
  import PhaseSection from "$lib/components/job/PhaseSection.svelte";
  import StageRow from "$lib/components/job/StageRow.svelte";
  import DeliverableRow from "$lib/components/job/DeliverableRow.svelte";
  import JourneyTrack from "$lib/components/job/JourneyTrack.svelte";
  import CumulativeStats from "$lib/components/job/CumulativeStats.svelte";
  import { PHASES, PARALLEL_STAGE_GROUPS, getNarrativeText, CELEBRATION_TIERS } from "$lib/components/job/phaseConfig";
  import type { PhaseStatus } from "$lib/components/job/phaseConfig";
  import { computeCumulativeStats } from "$lib/components/job/artifactParsers";
  import { STAGE_MAP, REPORT_ICON } from "$lib/config/billable-stages";
  import { getSolutions } from "$lib/api";
  import ShareDiscoveryModal from "$lib/components/ShareDiscoveryModal.svelte";

  let job = $state<Job | null>(null);
  let loading = $state(true);
  let error = $state("");
  let unsubscribeSSE: (() => void) | null = null;
  let cancelling = $state(false);
  let cancelError = $state("");
  let isResuming = $state(false);
  let resumeError = $state("");
  let showTechnicalDetails = $state(false);
  let generatingLanding = $state(false);
  let landingError = $state("");
  let landingInsufficientCredits = $state(false);
  let localSolutions = $state<SolutionPreview[] | null>(null);
  let hasPlayedReveal = $state(false);
  let showReveal = $state(false);
  let reportSummary = $state<ReportSummary | null>(null);
  let summaryFetched = $state(false);
  let summaryLoading = $state(false);
  let discoveryShareOpen = $state(false);
  let solutionVotes = $state<Record<string, number>>({});

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

  const isInteractiveJob = $derived(job?.jobMode === 'interactive');
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
    if (job && !shouldKeepSSEOpen(job)) return;

    unsubscribeSSE = subscribeToProgress(
      jobId,
      (data) => {
        if (data && data.id) {
          job = data as Job;
          if (data.solutionIdeas) {
            if (!localSolutions || data.solutionIdeas.length !== localSolutions.length) {
              localSolutions = data.solutionIdeas as SolutionPreview[];
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
      if (info.isShared && info.solutionVotes) {
        solutionVotes = info.solutionVotes;
      } else {
        solutionVotes = {};
      }
    } catch {}
  }

  async function loadJob(id: string) {
    // Reset all state for the new job
    unsubscribeSSE?.();
    job = null;
    loading = true;
    error = "";
    cancelling = false;
    cancelError = "";
    isResuming = false;
    resumeError = "";
    showTechnicalDetails = false;
    generatingLanding = false;
    landingError = "";
    localSolutions = null;
    hasPlayedReveal = false;
    showReveal = false;
    reportSummary = null;
    summaryFetched = false;
    summaryLoading = false;
    solutionVotes = {};

    try {
      const res = await fetch(`/api/jobs/${id}`);
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || "Job not found");
      }
      job = await res.json();
    } catch (e) {
      error = e instanceof Error ? e.message : "Failed to load job";
    } finally {
      loading = false;
    }

    if (job?.status === 'COMPLETED' && id) {
      hasPlayedReveal = true;
      showReveal = true;
      const asset = (job.assets ?? []).find(a => a.type === 'REPORT_JSON');
      if (asset && !summaryFetched) {
        summaryFetched = true;
        summaryLoading = true;
        try { reportSummary = await getReportSummary(id); }
        catch { /* fallback to simple card */ }
        finally { summaryLoading = false; }
      }
    }

    if (
      job && id &&
      ["AWAITING_SELECTION", "REGENERATING"].includes(job.status)
    ) {
      try {
        const solData = await getSolutions(id);
        if (!localSolutions) { localSolutions = solData.solutionIdeas; }
      } catch {
        if (!localSolutions) { localSolutions = job.solutionIdeas ?? null; }
      }
      pollVotes(id);
    }

    if (job && shouldKeepSSEOpen(job)) { connectSSE(); }
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
      job = { ...job, status: "QUEUED", errorMessage: null, progress: updatedProgress };
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
    landingInsufficientCredits = false;
    try {
      const res = await fetch(`/api/jobs/${jobId}/generate-landing`, { method: "POST" });
      if (!res.ok) {
        const data = await res.json();
        if (res.status === 402 && data.code === "INSUFFICIENT_CREDITS") {
          landingError = `Insufficient credits for landing page (need ${(page.data.stageCosts as any)?.landing_page ?? 5})`;
          landingInsufficientCredits = true;
          await invalidateAll();
          return;
        }
        throw new Error(data.error || "Failed to generate landing page");
      }
      invalidateAll();
      const updatedRes = await fetch(`/api/jobs/${jobId}`);
      if (updatedRes.ok) { job = await updatedRes.json(); }
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
      job = { ...job, status: "CANCELLED", errorMessage: "Cancelled by user" };
      unsubscribeSSE?.();
    } catch (e) {
      cancelError = e instanceof Error ? e.message : "Failed to cancel job";
    } finally {
      cancelling = false;
    }
  }

  // Re-load whenever jobId changes (handles same-route navigation e.g. /jobs/old → /jobs/new)
  $effect(() => {
    if (jobId) {
      loadJob(jobId);
    }
    return () => { unsubscribeSSE?.(); };
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
      default: return status;
    }
  }

  async function handleSelectionComplete() {
    try {
      const res = await fetch(`/api/jobs/${jobId}`);
      if (res.ok) { job = await res.json(); }
      connectSSE();
    } catch (e) {
      console.warn('Failed to refresh job after selection:', e);
    }
    invalidateAll();
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

  // Phase-level derived state
  const discoveryStages = $derived(
    displayStages.filter((s) => PHASES[0].stageNumbers.includes(s.stageNumber))
  );

  const analysisStages = $derived(
    displayStages.filter((s) => PHASES[1].stageNumbers.includes(s.stageNumber))
  );

  function computePhaseStatus(
    stagesInPhase: StageProgress[],
    phaseId: 'discovery' | 'analysis',
    jobStatus: string,
  ): PhaseStatus {
    if (stagesInPhase.length === 0) {
      // Analysis phase with no stages yet
      if (phaseId === 'analysis') {
        if (['AWAITING_SELECTION', 'REGENERATING'].includes(jobStatus)) return 'locked';
        if (['RUNNING_PHASE2'].includes(jobStatus)) return 'active';
      }
      return 'pending';
    }
    const hasRunning = stagesInPhase.some((s) => s.status === 'RUNNING');
    const hasFailed = stagesInPhase.some((s) => s.status === 'FAILED');
    const allCompleted = stagesInPhase.every((s) => s.status === 'COMPLETED' || s.status === 'SKIPPED');
    const anyCompleted = stagesInPhase.some((s) => s.status === 'COMPLETED');

    if (hasFailed) return 'failed';
    if (allCompleted) return 'completed';
    if (hasRunning) return 'active';
    if (anyCompleted) return 'active'; // some done, some pending
    // For analysis phase: locked until selection is done
    if (phaseId === 'analysis' && isInteractiveJob) {
      const gateStatus = computeGateStatus(jobStatus);
      if (gateStatus === 'locked' || gateStatus === 'active') return 'locked';
    }
    return 'pending';
  }

  function computeGateStatus(jobStatus: string): 'locked' | 'active' | 'passed' {
    if (['AWAITING_SELECTION', 'REGENERATING'].includes(jobStatus)) return 'active';
    if (['RUNNING_PHASE2', 'COMPLETED'].includes(jobStatus)) return 'passed';
    // Phase-2 queued: QUEUED with selections already made
    if (jobStatus === 'QUEUED' && (job?.selectedSolutions?.length ?? 0) > 0) return 'passed';
    // Regen-queued: QUEUED but already has solution ideas from phase 1
    if (jobStatus === 'QUEUED' && (job?.solutionIdeas?.length ?? 0) > 0) return 'active';
    return 'locked';
  }

  // During regeneration, keep Discovery collapsed — stage 5 re-runs
  // but the user should stay focused on the solution proposals list.
  const discoveryStatus = $derived<PhaseStatus>(
    job
      ? (job.status === 'REGENERATING' || isRegenQueued)
        ? 'completed'
        : computePhaseStatus(discoveryStages, 'discovery', job.status)
      : 'pending'
  );

  const analysisStatus = $derived<PhaseStatus>(
    job ? computePhaseStatus(analysisStages, 'analysis', job.status) : 'locked'
  );

  const gateStatus = $derived(job ? computeGateStatus(job.status) : 'locked');

  // Artifact subsets for PhaseResultsCard
  const discoveryArtifacts = $derived.by(() => {
    const result: Record<number, Record<string, any>> = {};
    for (const num of [1, 2, 3, 4]) {
      if (stageArtifacts[num]) result[num] = stageArtifacts[num];
    }
    return result;
  });

  const showDiscoveryCard = $derived(
    Object.keys(discoveryArtifacts).length > 0 &&
    job?.status !== 'PENDING' && job?.status !== 'QUEUED'
  );

  const showSelectedSummary = $derived(
    (job?.selectedSolutions?.length ?? 0) > 0 &&
    (job?.solutionIdeas?.length ?? 0) > 0
  );

  // Cumulative stats
  const cumulativeStats = $derived(computeCumulativeStats(stageArtifacts));

  // Journey track phase nodes
  const journeyPhases = $derived([
    { id: 'discovery', label: 'Discovery', status: discoveryStatus },
    { id: 'analysis', label: 'Analysis', status: analysisStatus },
  ]);

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
      .then(s => { reportSummary = s; })
      .catch(() => { /* fallback to simple card */ })
      .finally(() => { summaryLoading = false; });
  });

</script>

<svelte:head>
  <title>{job ? `Job ${job.status}` : "Loading..."} - NicheIQ</title>
</svelte:head>

<div class="py-8">
  <div class="page-container">
    {#if loading}
      <div class="text-center py-12 animate-fade-slide-in">
        <Loader2 class="w-10 h-10 text-accent mx-auto animate-spin" />
        <p class="mt-4 text-text-secondary">Loading job status...</p>
      </div>
    {:else if error}
      <div class="card p-8 text-center animate-fade-slide-in">
        <div class="p-3 rounded-xl bg-error/10 border border-error/20 w-fit mx-auto">
          <AlertTriangle class="w-8 h-8 text-error" />
        </div>
        <h2 class="mt-4 text-xl font-semibold text-text-primary">Error</h2>
        <p class="mt-2 text-text-secondary">{error}</p>
        <Button onclick={() => (showNewResearchModal.open = true)} label="Start New Research" class="mt-6 btn-primary inline-block" />
      </div>
    {:else if job}
      <!-- Header -->
      <div class="mb-8 animate-fade-slide-in">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="flex items-center gap-4">
            <div class="p-2.5 rounded-xl bg-accent/10 border border-accent/20">
              <Telescope class="w-5 h-5 text-accent" />
            </div>
            <div>
              <h1 class="text-2xl font-bold text-text-primary">Research Progress</h1>
              <p class="mt-1 text-sm text-text-muted truncate" title={job.niche}>
                {job.niche.length > 100 ? job.niche.substring(0, 100) + "..." : job.niche}
              </p>
            </div>
          </div>
          <div class="flex items-center gap-3 w-full sm:w-auto justify-end">
            {#if ["QUEUED", "PENDING", "RUNNING"].includes(job.status) && !(job.solutionIdeas?.length)}
              <SubmitButton onclick={cancelJob} loading={cancelling} loadingText="Cancelling..." icon={X} label="Cancel" class="btn-secondary btn-sm whitespace-nowrap text-error border-error/30 hover:bg-error/10 hover:border-error disabled:opacity-50 disabled:cursor-not-allowed" />
            {/if}
            {#if isCompleted && reportAsset}
              <Button href="/jobs/{job.id}/report" icon={REPORT_ICON} label="View Report" class="btn-primary btn-sm" />
            {/if}
            <Badge variant={getStatusVariant(isRegenQueued ? "REGENERATING" : job.status)}>
              {#if ["RUNNING", "RUNNING_PHASE2", "REGENERATING"].includes(job.status) || isRegenQueued}
                <Loader2 class="w-3.5 h-3.5 animate-spin" />
              {/if}
              {getStatusLabel(isRegenQueued ? "REGENERATING" : job.status)}
            </Badge>
          </div>
        </div>
        {#if cancelError}
          <div class="mt-3 text-sm text-error">{cancelError}</div>
        {/if}
      </div>

      <!-- Queue Position (for QUEUED jobs, but not regen-queued which shows inline) -->
      {#if (job.status === "QUEUED" || job.status === "PENDING") && !isRegenQueued}
        <div class="card p-6 mb-6 bg-warning/5 border-warning/20 animate-fade-slide-in" style="animation-delay: 100ms;">
          <div class="flex items-center gap-4">
            <div class="p-3 rounded-full bg-warning/10 border border-warning/20">
              <Clock class="w-6 h-6 text-warning" />
            </div>
            <div>
              <p class="font-semibold text-text-primary text-lg">
                {#if job.queuePosition === 1}
                  You're next!
                {:else if job.queuePosition && job.aheadCount}
                  {job.aheadCount} {job.aheadCount === 1 ? "report" : "reports"} ahead of you
                {:else}
                  Waiting in queue...
                {/if}
              </p>
              {#if job.queuePosition}
                <p class="text-sm text-text-muted mt-0.5">
                  Position {job.queuePosition} of {job.totalQueued} in queue
                </p>
              {/if}
            </div>
          </div>
        </div>
      {:else if showReveal && reportAsset}
        <!-- Report Teaser (replaces journey track for completed jobs) -->
        {#if summaryLoading}
          <div class="teaser-skeleton">
            <div class="teaser-skeleton-ring"></div>
            <div class="teaser-skeleton-content">
              <div class="teaser-skeleton-line teaser-skeleton-line--wide"></div>
              <div class="teaser-skeleton-line teaser-skeleton-line--medium"></div>
              <div class="teaser-skeleton-metrics">
                <div class="teaser-skeleton-metric"></div>
                <div class="teaser-skeleton-metric"></div>
                <div class="teaser-skeleton-metric"></div>
                <div class="teaser-skeleton-metric"></div>
              </div>
            </div>
          </div>
        {:else if reportSummary}
          {@const verdict = reportSummary.verdict?.toLowerCase() ?? ''}
          {@const verdictColor = verdict === 'go' ? 'success' : verdict === 'no-go' ? 'error' : 'warning'}
          <div class="teaser-card teaser-card--{verdictColor}">
            <div class="teaser-layout">
              <!-- Left: Score + Verdict -->
              <div class="teaser-score-col">
                {#if reportSummary.opportunity_score != null}
                  <ProgressRing
                    value={reportSummary.opportunity_score > 1 ? reportSummary.opportunity_score / 100 : reportSummary.opportunity_score}
                    size={80}
                    strokeWidth={6}
                    color="auto"
                    showValue={true}
                    flat={true}
                    showTooltip={false}
                  />
                {/if}
                <Badge variant={verdictColor === 'success' ? 'success' : verdictColor === 'error' ? 'error' : 'warning'}>
                  {#if verdict === 'go'}
                    <CheckCircle class="w-3.5 h-3.5" />
                  {:else if verdict === 'no-go'}
                    <XCircle class="w-3.5 h-3.5" />
                  {:else}
                    <AlertTriangle class="w-3.5 h-3.5" />
                  {/if}
                  {reportSummary.verdict ?? 'Unknown'}
                </Badge>
                {#if reportSummary.risk_level}
                  <span class="teaser-risk">{reportSummary.risk_level} Risk</span>
                {/if}
              </div>

              <!-- Right: Solution + Metrics + CTA -->
              <div class="teaser-details-col">
                <div class="teaser-solution">
                  {#if reportSummary.solution_name}
                    <h2 class="teaser-solution-name">{reportSummary.solution_name}</h2>
                  {/if}
                  {#if reportSummary.solution_tagline}
                    <p class="teaser-solution-tagline">{reportSummary.solution_tagline}</p>
                  {/if}
                  {#if reportSummary.project_type}
                    <span class="teaser-project-type">{reportSummary.project_type}</span>
                  {/if}
                </div>

                <div class="teaser-metrics">
                  {#if reportSummary.total_search_volume != null}
                    <div class="teaser-metric">
                      <span class="teaser-metric-value">{reportSummary.total_search_volume.toLocaleString()}</span>
                      <span class="teaser-metric-label">Search Vol</span>
                    </div>
                  {/if}
                  {#if reportSummary.competitor_count != null}
                    <div class="teaser-metric">
                      <span class="teaser-metric-value">{reportSummary.competitor_count}</span>
                      <span class="teaser-metric-label">Competitors</span>
                    </div>
                  {/if}
                  {#if reportSummary.total_keywords != null}
                    <div class="teaser-metric">
                      <span class="teaser-metric-value">{reportSummary.total_keywords}</span>
                      <span class="teaser-metric-label">Keywords</span>
                    </div>
                  {/if}
                  {#if reportSummary.pain_points_found != null}
                    <div class="teaser-metric">
                      <span class="teaser-metric-value">{reportSummary.pain_points_found}</span>
                      <span class="teaser-metric-label">Pain Points</span>
                    </div>
                  {/if}
                </div>

                <div class="teaser-cta">
                  <Button href="/jobs/{job.id}/report" icon={REPORT_ICON} label="View Full Report" class="btn-primary reveal-btn" />
                </div>
              </div>
            </div>
          </div>
        {:else}
          <!-- Fallback: simple card while summary not available -->
          <div class="reveal-container">
            <div class="reveal-check">
              <CheckCircle class="w-12 h-12 text-success" />
            </div>
            <h2 class="reveal-title">Your Research Report is Ready</h2>
            {#if cumulativeStats.some((s) => s.value != null)}
              <div class="reveal-stats">
                {#each cumulativeStats.filter((s) => s.value != null) as stat, i}
                  <div class="reveal-stat">
                    <span class="reveal-stat-value">{stat.value?.toLocaleString()}</span>
                    <span class="reveal-stat-label">{stat.label}</span>
                  </div>
                {/each}
              </div>
            {/if}
            <div class="reveal-cta">
              <Button href="/jobs/{job.id}/report" icon={REPORT_ICON} label="View Full Report" class="btn-primary reveal-btn" />
            </div>
          </div>
        {/if}
      {:else}
        <!-- Journey Track + Progress Bar + Cumulative Stats -->
        <div class="card p-6 mb-6 animate-fade-slide-in" style="animation-delay: 100ms;">
          <JourneyTrack
            phases={journeyPhases}
            gateStatus={isInteractiveJob ? gateStatus : 'passed'}
            isInteractive={isInteractiveJob}
            currentStageName={displayCurrentStageName}
            progressPercent={job.progressPercent}
            stagesCompleted={adjustedStagesCompleted}
            totalStages={adjustedTotalStages}
            isRunning={job.status === 'RUNNING' || job.status === 'RUNNING_PHASE2'}
            isFailed={job.status === 'FAILED'}
          />
          <CumulativeStats stats={cumulativeStats} />
        </div>
      {/if}

      <!-- Error / Cancelled / Resume (above phases, full width) -->
      {#if job.status === "CANCELLED"}
        <div class="p-4 rounded-lg bg-bg-elevated border border-border mb-6 animate-fade-slide-in" style="animation-delay: 150ms;">
          <div class="flex items-start gap-3">
            <div class="p-2 rounded-lg bg-text-muted/10 shrink-0">
              <XCircle class="w-5 h-5 text-text-muted" />
            </div>
            <div class="flex-1">
              <h3 class="text-sm font-medium text-text-secondary">Research Cancelled</h3>
              <p class="mt-1 text-sm text-text-muted">This research was cancelled. Your credits have been refunded.</p>
              <button
                onclick={() => (showNewResearchModal.open = true)}
                class="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-accent hover:text-accent-hover transition-colors"
              >
                Start new research
                <ArrowRight class="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      {/if}

      {#if job.status === "FAILED" && job.stopReason === "INSUFFICIENT_DATA"}
        <div class="p-5 rounded-lg bg-warning/5 border border-warning/20 mb-6 animate-fade-slide-in" style="animation-delay: 150ms;">
          <div class="flex items-start gap-4">
            <div class="p-2.5 rounded-xl bg-warning/10 border border-warning/20 shrink-0">
              <AlertTriangle class="w-6 h-6 text-warning" />
            </div>
            <div class="flex-1">
              <h3 class="text-base font-semibold text-text-primary">Not Enough Data Found</h3>
              <p class="mt-1.5 text-sm text-text-secondary">
                {job.stopReasonDetails?.recommendation || "The research could not continue due to insufficient discussion data."}
              </p>
              {#if job.stopReasonDetails?.metrics}
                <div class="mt-4 p-3 rounded-lg bg-bg-surface border border-border">
                  <div class="text-xs font-medium text-text-muted uppercase tracking-wide mb-2">Quality Metrics</div>
                  <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
                    <div>
                      <span class="text-text-muted">Pain Points:</span>
                      <span class="ml-1 font-medium text-text-primary">{job.stopReasonDetails.metrics.painPointCount ?? 0}</span>
                    </div>
                    <div>
                      <span class="text-text-muted">Quality:</span>
                      <span class="ml-1 font-medium text-text-primary">
                        {job.stopReasonDetails.confidenceScore
                          ? `${(job.stopReasonDetails.confidenceScore * 100).toFixed(0)}%`
                          : "N/A"}
                      </span>
                    </div>
                    <div>
                      <span class="text-text-muted">Coverage:</span>
                      <span class="ml-1 font-medium text-text-primary">
                        {job.stopReasonDetails.metrics.sourceCoverage
                          ? `${(job.stopReasonDetails.metrics.sourceCoverage * 100).toFixed(0)}%`
                          : "N/A"}
                      </span>
                    </div>
                  </div>
                </div>
              {/if}
              <div class="mt-4 flex items-center gap-2">
                <CheckCircle class="w-4 h-4 text-success" />
                <span class="text-sm text-success">Credits refunded automatically</span>
              </div>
            </div>
          </div>
        </div>
      {:else if job.status === "FAILED" && (job.errorDetails || job.errorMessage)}
        {@const severity = job.errorDetails?.severity || "error"}
        {@const bgColor = severity === "info" ? "bg-info/5" : severity === "warning" ? "bg-warning/5" : "bg-error/5"}
        {@const borderColor = severity === "info" ? "border-info/20" : severity === "warning" ? "border-warning/20" : "border-error/20"}
        {@const iconBg = severity === "info" ? "bg-info/10" : severity === "warning" ? "bg-warning/10" : "bg-error/10"}
        {@const iconColor = severity === "info" ? "text-info" : severity === "warning" ? "text-warning" : "text-error"}
        {@const textColor = severity === "info" ? "text-info" : severity === "warning" ? "text-warning" : "text-error"}

        <div class="p-4 rounded-lg {bgColor} border {borderColor} mb-6 animate-fade-slide-in" style="animation-delay: 150ms;">
          <div class="flex items-start gap-3">
            <div class="p-2 rounded-lg {iconBg} shrink-0">
              {#if severity === "info"}
                <AlertTriangle class="w-5 h-5 {iconColor}" />
              {:else if severity === "warning"}
                <AlertTriangle class="w-5 h-5 {iconColor}" />
              {:else}
                <XCircle class="w-5 h-5 {iconColor}" />
              {/if}
            </div>
            <div class="flex-1">
              {#if job.errorDetails}
                <h3 class="text-sm font-medium {textColor}">{job.errorDetails.userMessage}</h3>
                <p class="mt-1 text-sm text-text-muted">{job.errorDetails.actionableGuidance}</p>
                {#if job.errorDetails.retryDelayMinutes}
                  <p class="mt-2 text-xs text-text-muted">Suggested wait time: {job.errorDetails.retryDelayMinutes} minutes</p>
                {/if}
                {#if job.errorMessage}
                  <button
                    type="button"
                    class="mt-3 text-xs text-text-muted hover:text-text-secondary underline"
                    onclick={() => (showTechnicalDetails = !showTechnicalDetails)}
                  >
                    {showTechnicalDetails ? "Hide" : "Show"} technical details
                  </button>
                  {#if showTechnicalDetails}
                    <div class="mt-2 p-3 rounded bg-bg-elevated border border-border text-xs font-mono text-text-muted overflow-x-auto">
                      <pre class="whitespace-pre-wrap break-words">{job.errorMessage}</pre>
                    </div>
                  {/if}
                {/if}
              {:else}
                <h3 class="text-sm font-medium {textColor}">Error</h3>
                <p class="mt-1 text-sm text-text-muted">{job.errorMessage}</p>
              {/if}
            </div>
          </div>
        </div>
      {/if}

      {#if job.status === "FAILED"}
        <div class="card p-6 mb-6 animate-fade-slide-in" style="animation-delay: 175ms;">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 class="text-sm font-medium text-text-primary">Resume from Checkpoint</h3>
              <p class="mt-1 text-sm text-text-muted">Continue where you left off. The refunded credits will be re-charged.</p>
            </div>
            <SubmitButton onclick={resumeJob} loading={isResuming} loadingText="Resuming..." icon={RotateCw} keepIconOnLoad label="Resume" class="btn-primary flex items-center gap-2" />
          </div>
          {#if resumeError}
            <p class="mt-3 text-sm text-error">{resumeError}</p>
          {/if}
        </div>
      {/if}

      <!-- ===== Phases ===== -->
      <div class="phases-column">
          <!-- Phase 1: Discovery -->
          <PhaseSection
            title="Discovery"
            icon={PHASES[0].icon}
            status={discoveryStatus}
            stagesCompleted={discoveryStages.filter((s) => s.status === 'COMPLETED' || s.status === 'SKIPPED').length}
            stagesTotal={discoveryStages.length || PHASES[0].stageNumbers.length}
            defaultOpen={discoveryStatus === 'active'}
          >
            <div class="stage-list">
              {#each discoveryStages as stage, i (stage.stageNumber)}
                <StageRow
                  {stage}
                  narrativeText={getNarrativeText(stage.stageNumber, stage.status, stageArtifacts[stage.stageNumber])}
                  isLast={i === discoveryStages.length - 1}
                  celebrationTier={CELEBRATION_TIERS[stage.stageNumber] ?? 1}
                />
              {/each}
            </div>

            {#if showDiscoveryCard}
              <div class="mt-3">
                <PhaseResultsCard phase="discovery" artifacts={discoveryArtifacts} />
              </div>
            {/if}
          </PhaseSection>

          <!-- Selection Gate (interactive jobs only) -->
          {#if isInteractiveJob}
            {#if job.status === "AWAITING_SELECTION" || job.status === "REGENERATING" || isRegenQueued}
              {#if job.status === "AWAITING_SELECTION" && displaySolutions.length > 0}
                <div class="mb-2 flex justify-end">
                  <button
                    onclick={() => (discoveryShareOpen = true)}
                    class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-border text-text-secondary hover:text-text-primary hover:bg-bg-hover transition-colors"
                  >
                    <Share2 class="w-3.5 h-3.5" />
                    Share Discovery
                  </button>
                </div>
              {/if}
              <div class="mb-3 animate-fade-slide-in">
                <SolutionSelectionView
                  jobId={jobId ?? ''}
                  solutions={displaySolutions}
                  selectedSolution={job.selectedSolution}
                  selectedSolutions={job.selectedSolutions}
                  isRegenerating={job.status === "REGENERATING" || isRegenQueued}
                  canRegenerate={job.canRegenerate ?? false}
                  stageCosts={page.data.stageCosts}
                  creditBalance={page.data.creditBalance}
                  onSelectionComplete={handleSelectionComplete}
                  onRegenerateStart={() => { job = { ...job!, status: "QUEUED" }; }}
                  {solutionVotes}
                />
              </div>
            {:else if showSelectedSummary}
              <div class="mb-3 animate-fade-slide-in">
                <SelectedSolutionsSummary
                  selectedNames={job.selectedSolutions ?? []}
                  solutionIdeas={job.solutionIdeas ?? []}
                  primaryWinner={job.selectedSolution}
                  status={job.status}
                />
              </div>
            {:else if gateStatus === 'locked'}
              {@const GateIcon = PHASES[1].icon}
              <div class="gate-locked mb-3">
                <div class="gate-locked-inner">
                  <GateIcon class="w-4 h-4 text-text-muted" />
                  <span class="text-sm text-text-muted">Solution selection unlocks after discovery</span>
                </div>
              </div>
            {/if}
          {:else}
            <!-- Non-interactive: show selected summary if present -->
            {#if showSelectedSummary}
              <div class="mb-3 animate-fade-slide-in">
                <SelectedSolutionsSummary
                  selectedNames={job.selectedSolutions ?? []}
                  solutionIdeas={job.solutionIdeas ?? []}
                  primaryWinner={job.selectedSolution}
                  status={job.status}
                />
              </div>
            {:else if gateStatus === 'locked'}
              {@const GateIcon = PHASES[1].icon}
              <div class="gate-locked mb-3">
                <div class="gate-locked-inner">
                  <GateIcon class="w-4 h-4 text-text-muted" />
                  <span class="text-sm text-text-muted">Solution selection unlocks after discovery</span>
                </div>
              </div>
            {:else}
              <!-- gateStatus is 'passed' but no summary data (auto-selection) — intentionally empty -->
            {/if}
          {/if}

          <!-- Phase 2: Deep Analysis -->
          <PhaseSection
            title="Deep Analysis"
            icon={PHASES[1].icon}
            status={analysisStatus}
            stagesCompleted={analysisStages.filter((s) => s.status === 'COMPLETED' || s.status === 'SKIPPED').length}
            stagesTotal={analysisStages.length || PHASES[1].stageNumbers.length}
            defaultOpen={analysisStatus === 'active'}
            creditCost={analysisStatus === 'locked' || analysisStatus === 'pending'
              ? (page.data.stageCosts as any)?.deep_research ?? 0
              : 0}
          >
            <div class="stage-list">
              {#each analysisStages as stage, i (stage.stageNumber)}
                <StageRow
                  {stage}
                  narrativeText={getNarrativeText(stage.stageNumber, stage.status, stageArtifacts[stage.stageNumber])}
                  isLast={i === analysisStages.length - 1}
                  celebrationTier={CELEBRATION_TIERS[stage.stageNumber] ?? 1}
                />
              {/each}
            </div>

          </PhaseSection>
      </div>

      <!-- Extras -->
      {#if job}
        <div class="extras-card {lpStatus === 'locked' ? 'extras-card--locked' : ''} animate-fade-slide-in" style="animation-delay: 300ms;">
          <div class="extras-header">
            <div class="extras-header-left">
              <div class="extras-icon-box">
                <Package class="extras-icon" />
              </div>
              <div class="extras-title-group">
                <span class="extras-title">Extras</span>
                <span class="extras-subtitle">Add-on deliverables for your research</span>
              </div>
            </div>
            {#if lpStatus === 'completed'}
              <span class="extras-ready-badge">
                <CheckCircle class="extras-ready-icon" />
                Ready
              </span>
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
              isInsufficientCredits={landingInsufficientCredits}
              onGenerate={generateLanding}
            />
          </div>
        </div>
      {/if}

      <!-- Meta Info -->
      <div class="mt-6 p-4 rounded-lg bg-bg-surface border border-border animate-fade-slide-in" style="animation-delay: 350ms;">
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
  </div>
</div>

{#if jobId}
  <ShareDiscoveryModal bind:open={discoveryShareOpen} jobId={jobId} />
{/if}

<style>
  .page-container {
    max-width: 72rem; /* wider to accommodate two columns */
    margin: 0 auto;
    padding: 0 1rem;
  }

  @media (min-width: 640px) {
    .page-container {
      padding: 0 1.5rem;
    }
  }

  @media (min-width: 1024px) {
    .page-container {
      padding: 0 2rem;
    }
  }

  .phases-column {
    min-width: 0;
    margin-bottom: 1.5rem;
  }

  .phases-column :global(.insight-card--border-left) {
    border-left: none;
    background: var(--color-bg-elevated);
    background-image: none;
  }

  .stage-list {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
    padding: 0.25rem 0;
    position: relative;
  }


  .gate-locked {
    border: 1px dashed var(--color-border);
    border-radius: 0.75rem;
    padding: 1rem 1.25rem;
    opacity: 0.55;
  }

  .gate-locked-inner {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  /* ===== Report-Ready Reveal ===== */
  .reveal-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    padding: 2.5rem 1.5rem;
    margin-bottom: 1.5rem;
    background: var(--color-bg-elevated);
    border: 1px solid rgba(34, 197, 94, 0.3);
    border-radius: 0.75rem;
    animation: reveal-fade-in 500ms ease-out;
  }

  @keyframes reveal-fade-in {
    0% { opacity: 0; transform: translateY(10px); }
    100% { opacity: 1; transform: translateY(0); }
  }

  .reveal-check {
    margin-bottom: 1.25rem;
  }

  .reveal-title {
    font-family: var(--font-display);
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--color-text-primary);
    margin-bottom: 1.25rem;
  }

  .reveal-stats {
    display: flex;
    gap: 2rem;
    margin-bottom: 1.5rem;
    flex-wrap: wrap;
    justify-content: center;
  }

  .reveal-stat {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.25rem;
  }

  .reveal-stat-value {
    font-family: var(--font-mono);
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--color-accent);
  }

  .reveal-stat-label {
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }


  @media (prefers-reduced-motion: reduce) {
    .reveal-container { animation: none; }
    .teaser-card { animation: none; }
  }

  /* ===== Report Teaser Card ===== */
  .teaser-card {
    padding: 1.75rem;
    margin-bottom: 1.5rem;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: 0.75rem;
    animation: reveal-fade-in 500ms ease-out;
  }

  .teaser-card--success {
    border-color: rgba(34, 197, 94, 0.35);
    background-image: linear-gradient(135deg, rgba(34, 197, 94, 0.05) 0%, transparent 40%);
  }

  .teaser-card--error {
    border-color: rgba(239, 68, 68, 0.35);
    background-image: linear-gradient(135deg, rgba(239, 68, 68, 0.05) 0%, transparent 40%);
  }

  .teaser-card--warning {
    border-color: rgba(234, 179, 8, 0.35);
    background-image: linear-gradient(135deg, rgba(234, 179, 8, 0.05) 0%, transparent 40%);
  }

  .teaser-layout {
    display: flex;
    gap: 2rem;
    align-items: flex-start;
  }

  .teaser-score-col {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.625rem;
    flex-shrink: 0;
  }

  .teaser-risk {
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .teaser-details-col {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .teaser-solution-name {
    font-family: var(--font-display);
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--color-text-primary);
    line-height: 1.3;
  }

  .teaser-solution-tagline {
    font-size: 0.875rem;
    font-style: italic;
    color: var(--color-text-muted);
    line-height: 1.4;
    margin-top: 0.25rem;
  }

  .teaser-project-type {
    display: inline-block;
    margin-top: 0.375rem;
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    padding: 0.125rem 0.5rem;
    border-radius: 9999px;
  }

  .teaser-metrics {
    display: flex;
    gap: 1.25rem;
    flex-wrap: wrap;
  }

  .teaser-metric {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
  }

  .teaser-metric-value {
    font-family: var(--font-mono);
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--color-accent);
    line-height: 1;
  }

  .teaser-metric-label {
    font-size: 0.6875rem;
    font-weight: 500;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .teaser-cta {
    padding-top: 0.25rem;
  }

  /* ===== Teaser Skeleton ===== */
  .teaser-skeleton {
    display: flex;
    gap: 2rem;
    align-items: flex-start;
    padding: 1.75rem;
    margin-bottom: 1.5rem;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: 0.75rem;
  }

  .teaser-skeleton-ring {
    width: 88px;
    height: 88px;
    border-radius: 50%;
    background: var(--color-bg-surface);
    flex-shrink: 0;
    animation: skeleton-pulse 1.5s ease-in-out infinite;
  }

  .teaser-skeleton-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .teaser-skeleton-line {
    height: 1rem;
    border-radius: 0.25rem;
    background: var(--color-bg-surface);
    animation: skeleton-pulse 1.5s ease-in-out infinite;
  }

  .teaser-skeleton-line--wide { width: 60%; }
  .teaser-skeleton-line--medium { width: 40%; animation-delay: 0.15s; }

  .teaser-skeleton-metrics {
    display: flex;
    gap: 1.25rem;
    margin-top: 0.5rem;
  }

  .teaser-skeleton-metric {
    width: 4rem;
    height: 2.5rem;
    border-radius: 0.375rem;
    background: var(--color-bg-surface);
    animation: skeleton-pulse 1.5s ease-in-out infinite;
  }

  .teaser-skeleton-metric:nth-child(2) { animation-delay: 0.1s; }
  .teaser-skeleton-metric:nth-child(3) { animation-delay: 0.2s; }
  .teaser-skeleton-metric:nth-child(4) { animation-delay: 0.3s; }

  @keyframes skeleton-pulse {
    0%, 100% { opacity: 0.4; }
    50% { opacity: 0.7; }
  }

  /* ===== Responsive: mobile stack ===== */
  @media (max-width: 639px) {
    .teaser-layout {
      flex-direction: column;
      align-items: center;
      text-align: center;
    }

    .teaser-details-col {
      align-items: center;
    }

    .teaser-metrics {
      justify-content: center;
    }

    .teaser-cta {
      align-self: center;
    }

    .teaser-skeleton {
      flex-direction: column;
      align-items: center;
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

  .extras-card--locked {
    border-style: dashed;
    pointer-events: none;
  }

  .extras-card--locked .extras-header {
    opacity: 0.55;
  }

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
    background: rgba(229, 90, 40, 0.1);
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
    background: rgba(34, 197, 94, 0.1);
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
</style>
