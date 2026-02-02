<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { page } from '$app/stores';
  import { subscribeToProgress, isTerminalStatus, shouldKeepSSEOpen } from '$lib/api';
  import Badge from '$lib/components/ui/Badge.svelte';
  import {
    Loader2,
    AlertTriangle,
    XCircle,
    Clock,
    CheckCircle,
    X,
    FileText,
    ExternalLink,
    Minus,
    ArrowRight,
    Activity,
    RotateCw,
    Globe
  } from 'lucide-svelte';
  import { showNewResearchModal } from '$lib/stores/newResearchModal';

  interface StageProgress {
    stageNumber: number;
    stageName: string;
    status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'SKIPPED' | 'FAILED';
    durationSeconds: number | null;
  }

  interface Asset {
    type: string;
    url: string;
  }

  interface StopReasonDetails {
    qualityTier?: string;
    confidenceScore?: number;
    metrics?: {
      painPointCount?: number;
      quoteDensity?: number;
      sourceCoverage?: number;
    };
    recommendation?: string;
  }

  type ErrorSeverity = 'info' | 'warning' | 'error';

  interface ErrorDetails {
    code: string;
    severity: ErrorSeverity;
    userMessage: string;
    actionableGuidance: string;
    retryDelayMinutes?: number;
    rawMessage?: string;
  }

  interface Job {
    id: string;
    email: string;
    niche: string;
    status: 'PENDING' | 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
    currentStage: number;
    currentStageName: string | null;
    stagesCompleted: number;
    totalStages: number;
    progressPercent: number;
    errorMessage: string | null;
    createdAt: string;
    startedAt: string | null;
    completedAt: string | null;
    progress: StageProgress[];
    assets: Asset[];
    // Queue position info (for QUEUED jobs)
    queuePosition?: number | null;
    aheadCount?: number;
    totalQueued?: number;
    // Quality gate stop metadata
    stopReason?: string | null;
    stopReasonDetails?: StopReasonDetails | null;
    // User-friendly error information
    errorCode?: string | null;
    errorDetails?: ErrorDetails | null;
    // Landing page lifecycle
    generateLandingPage?: boolean;
    landingPageStatus?: string | null;
  }

  let job = $state<Job | null>(null);
  let loading = $state(true);
  let error = $state('');
  let unsubscribeSSE: (() => void) | null = null;
  let cancelling = $state(false);
  let cancelError = $state('');
  let isResuming = $state(false);
  let resumeError = $state('');
  let showTechnicalDetails = $state(false);
  let generatingLanding = $state(false);
  let landingError = $state('');

  const jobId = $derived($page.params.jobId);

  function connectSSE() {
    // Clean up existing subscription
    unsubscribeSSE?.();

    // Don't connect if no jobId or job is fully terminal (no landing in progress)
    if (!jobId) return;
    if (job && !shouldKeepSSEOpen(job)) return;

    unsubscribeSSE = subscribeToProgress(
      jobId,
      (data) => {
        if (data && data.id) {
          job = data as Job;
        }
      },
      (err) => console.warn('SSE error:', err.message)
    );
  }

  async function resumeJob() {
    if (!job || isResuming) return;

    isResuming = true;
    resumeError = '';

    try {
      const res = await fetch(`/api/jobs/${jobId}/resume`, {
        method: 'POST',
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || 'Failed to resume job');
      }

      // Update local state to show it's queued again
      // Reset any FAILED or RUNNING stages to PENDING for proper visual feedback
      const updatedProgress = job.progress.map(stage =>
        (stage.status === 'FAILED' || stage.status === 'RUNNING')
          ? { ...stage, status: 'PENDING' as const }
          : stage
      );
      job = { ...job, status: 'QUEUED', errorMessage: null, progress: updatedProgress };

      // Reconnect SSE for real-time updates
      connectSSE();
    } catch (e) {
      resumeError = e instanceof Error ? e.message : 'Failed to resume job';
    } finally {
      isResuming = false;
    }
  }

  async function generateLanding() {
    if (!job || generatingLanding) return;

    generatingLanding = true;
    landingError = '';

    try {
      const res = await fetch(`/api/jobs/${jobId}/generate-landing`, {
        method: 'POST',
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || 'Failed to generate landing page');
      }

      // Refetch job to get updated state (landingPageStatus, new stage 11)
      const updatedRes = await fetch(`/api/jobs/${jobId}`);
      if (updatedRes.ok) {
        job = await updatedRes.json();
      }

      // Reconnect SSE for real-time landing page progress
      connectSSE();
    } catch (e) {
      landingError = e instanceof Error ? e.message : 'Failed to generate landing page';
    } finally {
      generatingLanding = false;
    }
  }

  async function cancelJob() {
    if (!job || cancelling) return;

    cancelling = true;
    cancelError = '';

    try {
      const res = await fetch(`/api/jobs/${jobId}/cancel`, {
        method: 'POST',
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || 'Failed to cancel job');
      }

      // Update local state
      job = { ...job, status: 'CANCELLED', errorMessage: 'Cancelled by user' };

      // Close SSE connection
      unsubscribeSSE?.();
    } catch (e) {
      cancelError = e instanceof Error ? e.message : 'Failed to cancel job';
    } finally {
      cancelling = false;
    }
  }

  onMount(async () => {
    // Initial fetch
    try {
      const res = await fetch(`/api/jobs/${jobId}`);
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || 'Job not found');
      }
      job = await res.json();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load job';
    } finally {
      loading = false;
    }

    // SSE for real-time updates if job is still in progress or landing page is generating
    if (job && shouldKeepSSEOpen(job)) {
      connectSSE();
    }
  });

  onDestroy(() => {
    unsubscribeSSE?.();
  });

  function getStatusVariant(status: string): 'success' | 'warning' | 'error' | 'muted' | 'info' {
    switch (status) {
      case 'COMPLETED': return 'success';
      case 'RUNNING': return 'info';
      case 'FAILED': return 'error';
      case 'CANCELLED': return 'muted';
      default: return 'warning'; // PENDING, QUEUED
    }
  }

  function formatDuration(seconds: number | null): string {
    if (!seconds) return '';
    if (seconds < 60) return `${Math.round(seconds)}s`;

    // Use floor for both to avoid "60s" issue from rounding
    const totalSeconds = Math.round(seconds);
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${mins}m ${secs}s`;
  }

  // Stages that run in parallel and should be combined into one line
  const PARALLEL_STAGE_GROUPS: Record<number, { hide: number[], combinedName: string }> = {
    6: { hide: [6.5], combinedName: 'Pain Point & Audience Analysis' }
  };

  // Process stages to combine parallel stages into single lines
  function processStagesForDisplay(stages: StageProgress[], jobStatus: string): StageProgress[] {
    const hiddenStages = new Set<number>();

    // Collect all stages that should be hidden
    for (const group of Object.values(PARALLEL_STAGE_GROUPS)) {
      group.hide.forEach(s => hiddenStages.add(s));
    }

    return stages
      .filter(stage => !hiddenStages.has(stage.stageNumber))
      .map(stage => {
        const group = PARALLEL_STAGE_GROUPS[stage.stageNumber];
        let processed = group ? { ...stage, stageName: group.combinedName } : stage;
        // Safety net: terminal jobs shouldn't show spinning stages
        if ((jobStatus === 'FAILED' || jobStatus === 'CANCELLED') && processed.status === 'RUNNING') {
          processed = { ...processed, status: 'FAILED' };
        }
        return processed;
      });
  }

  const displayStages = $derived(job ? processStagesForDisplay(job.progress, job.status) : []);

  // Adjusted stage counts (subtract hidden stages)
  const adjustedStagesCompleted = $derived.by(() => {
    if (!job) return 0;
    const hiddenStageNumbers = Object.values(PARALLEL_STAGE_GROUPS).flatMap(g => g.hide);
    const hiddenCompleted = job.progress.filter(
      s => hiddenStageNumbers.includes(s.stageNumber) && s.status === 'COMPLETED'
    ).length;
    return job.stagesCompleted - hiddenCompleted;
  });

  const adjustedTotalStages = $derived.by(() => {
    if (!job) return 0;
    const hiddenCount = Object.values(PARALLEL_STAGE_GROUPS).flatMap(g => g.hide).length;
    return job.totalStages - hiddenCount;
  });
</script>

<svelte:head>
  <title>{job ? `Job ${job.status}` : 'Loading...'} - NicheIQ</title>
</svelte:head>

<div class="py-8">
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
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
        <button onclick={() => ($showNewResearchModal = true)} class="mt-6 btn-primary inline-block">Start New Research</button>
      </div>
    {:else if job}
      <!-- Header -->
      <div class="mb-8 animate-fade-slide-in">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-4">
            <div class="p-2.5 rounded-xl bg-accent/10 border border-accent/20">
              <Activity class="w-5 h-5 text-accent" />
            </div>
            <div>
              <h1 class="text-2xl font-bold text-text-primary">Research Progress</h1>
              <p class="mt-1 text-sm text-text-muted truncate max-w-xl" title={job.niche}>
                {job.niche.length > 100 ? job.niche.substring(0, 100) + '...' : job.niche}
              </p>
            </div>
          </div>
          <div class="flex items-center gap-3">
            {#if ['QUEUED', 'PENDING', 'RUNNING'].includes(job.status)}
              <button
                onclick={cancelJob}
                disabled={cancelling}
                class="btn-secondary btn-sm whitespace-nowrap text-error border-error/30 hover:bg-error/10 hover:border-error disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {#if cancelling}
                  <Loader2 class="w-4 h-4 animate-spin" />
                  Cancelling...
                {:else}
                  <X class="w-4 h-4" />
                  Cancel
                {/if}
              </button>
            {/if}
            <Badge variant={getStatusVariant(job.status)}>
              {#if job.status === 'RUNNING'}
                <Loader2 class="w-3.5 h-3.5 animate-spin" />
              {/if}
              {job.status}
            </Badge>
          </div>
        </div>
        {#if cancelError}
          <div class="mt-3 text-sm text-error">{cancelError}</div>
        {/if}
      </div>

      <!-- Queue Position (for QUEUED jobs) -->
      {#if job.status === 'QUEUED' || job.status === 'PENDING'}
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
                  {job.aheadCount} {job.aheadCount === 1 ? 'report' : 'reports'} ahead of you
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
      {:else}
        <!-- Progress Bar (for non-queued jobs) -->
        {@const displayCurrentStageName = (job.currentStage === 6 || job.currentStage === 6.5)
          ? PARALLEL_STAGE_GROUPS[6].combinedName
          : (job.currentStageName || 'Initializing...')}
        <div class="card p-6 mb-6 animate-fade-slide-in" style="animation-delay: 100ms;">
          <div class="flex justify-between items-center mb-3">
            <span class="text-sm font-medium text-text-secondary">
              {displayCurrentStageName}
            </span>
            <span class="text-sm font-semibold text-accent">
              {Math.round(job.progressPercent)}%
            </span>
          </div>
          <div class="progress-bar h-3">
            <div
              class="progress-bar-fill {job.status === 'RUNNING' ? 'animate-shimmer' : ''} {job.status === 'FAILED' ? 'progress-failed' : ''}"
              style="width: {job.progressPercent}%"
            ></div>
          </div>
          <p class="mt-3 text-sm text-text-muted">
            {adjustedStagesCompleted} of {adjustedTotalStages} stages completed
          </p>
        </div>
      {/if}

      <!-- Cancelled Message -->
      {#if job.status === 'CANCELLED'}
        <div class="p-4 rounded-lg bg-bg-elevated border border-border mb-6 animate-fade-slide-in" style="animation-delay: 150ms;">
          <div class="flex items-start gap-3">
            <div class="p-2 rounded-lg bg-text-muted/10 shrink-0">
              <XCircle class="w-5 h-5 text-text-muted" />
            </div>
            <div class="flex-1">
              <h3 class="text-sm font-medium text-text-secondary">Research Cancelled</h3>
              <p class="mt-1 text-sm text-text-muted">This research was cancelled. Your credit has been refunded.</p>
              <button onclick={() => ($showNewResearchModal = true)} class="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-accent hover:text-accent-hover transition-colors">
                Start new research
                <ArrowRight class="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      {/if}

      <!-- Quality Gate Stop Message (intentional stop, not an error) -->
      {#if job.status === 'FAILED' && job.stopReason === 'INSUFFICIENT_DATA'}
        <div class="p-5 rounded-lg bg-warning/5 border border-warning/20 mb-6 animate-fade-slide-in" style="animation-delay: 150ms;">
          <div class="flex items-start gap-4">
            <div class="p-2.5 rounded-xl bg-warning/10 border border-warning/20 shrink-0">
              <AlertTriangle class="w-6 h-6 text-warning" />
            </div>
            <div class="flex-1">
              <h3 class="text-base font-semibold text-text-primary">Not Enough Data Found</h3>
              <p class="mt-1.5 text-sm text-text-secondary">
                {job.stopReasonDetails?.recommendation || 'The research could not continue due to insufficient discussion data.'}
              </p>

              {#if job.stopReasonDetails?.metrics}
                <div class="mt-4 p-3 rounded-lg bg-bg-surface border border-border">
                  <div class="text-xs font-medium text-text-muted uppercase tracking-wide mb-2">Quality Metrics</div>
                  <div class="grid grid-cols-3 gap-4 text-sm">
                    <div>
                      <span class="text-text-muted">Pain Points:</span>
                      <span class="ml-1 font-medium text-text-primary">{job.stopReasonDetails.metrics.painPointCount ?? 0}</span>
                    </div>
                    <div>
                      <span class="text-text-muted">Quality:</span>
                      <span class="ml-1 font-medium text-text-primary">
                        {job.stopReasonDetails.confidenceScore ? `${(job.stopReasonDetails.confidenceScore * 100).toFixed(0)}%` : 'N/A'}
                      </span>
                    </div>
                    <div>
                      <span class="text-text-muted">Coverage:</span>
                      <span class="ml-1 font-medium text-text-primary">
                        {job.stopReasonDetails.metrics.sourceCoverage ? `${(job.stopReasonDetails.metrics.sourceCoverage * 100).toFixed(0)}%` : 'N/A'}
                      </span>
                    </div>
                  </div>
                </div>
              {/if}

              <div class="mt-4 flex items-center gap-2">
                <CheckCircle class="w-4 h-4 text-success" />
                <span class="text-sm text-success">Credit refunded automatically</span>
              </div>
            </div>
          </div>
        </div>

      <!-- Regular Error Message (for actual failures) -->
      {:else if job.status === 'FAILED' && (job.errorDetails || job.errorMessage)}
        {@const severity = job.errorDetails?.severity || 'error'}
        {@const bgColor = severity === 'info' ? 'bg-info/5' : severity === 'warning' ? 'bg-warning/5' : 'bg-error/5'}
        {@const borderColor = severity === 'info' ? 'border-info/20' : severity === 'warning' ? 'border-warning/20' : 'border-error/20'}
        {@const iconBg = severity === 'info' ? 'bg-info/10' : severity === 'warning' ? 'bg-warning/10' : 'bg-error/10'}
        {@const iconColor = severity === 'info' ? 'text-info' : severity === 'warning' ? 'text-warning' : 'text-error'}
        {@const textColor = severity === 'info' ? 'text-info' : severity === 'warning' ? 'text-warning' : 'text-error'}

        <div class="p-4 rounded-lg {bgColor} border {borderColor} mb-6 animate-fade-slide-in" style="animation-delay: 150ms;">
          <div class="flex items-start gap-3">
            <div class="p-2 rounded-lg {iconBg} shrink-0">
              {#if severity === 'info'}
                <AlertTriangle class="w-5 h-5 {iconColor}" />
              {:else if severity === 'warning'}
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
                  <p class="mt-2 text-xs text-text-muted">
                    Suggested wait time: {job.errorDetails.retryDelayMinutes} minutes
                  </p>
                {/if}

                <!-- Technical Details Toggle -->
                {#if job.errorMessage}
                  <button
                    type="button"
                    class="mt-3 text-xs text-text-muted hover:text-text-secondary underline"
                    onclick={() => showTechnicalDetails = !showTechnicalDetails}
                  >
                    {showTechnicalDetails ? 'Hide' : 'Show'} technical details
                  </button>

                  {#if showTechnicalDetails}
                    <div class="mt-2 p-3 rounded bg-bg-elevated border border-border text-xs font-mono text-text-muted overflow-x-auto">
                      <pre class="whitespace-pre-wrap break-words">{job.errorMessage}</pre>
                    </div>
                  {/if}
                {/if}
              {:else}
                <!-- Fallback for jobs without errorDetails (backward compatibility) -->
                <h3 class="text-sm font-medium {textColor}">Error</h3>
                <p class="mt-1 text-sm text-text-muted">{job.errorMessage}</p>
              {/if}
            </div>
          </div>
        </div>
      {/if}

      <!-- Resume Button for Failed Jobs -->
      {#if job.status === 'FAILED'}
        <div class="card p-6 mb-6 animate-fade-slide-in" style="animation-delay: 175ms;">
          <div class="flex items-center justify-between">
            <div>
              <h3 class="text-sm font-medium text-text-primary">Resume from Checkpoint</h3>
              <p class="mt-1 text-sm text-text-muted">Continue where you left off. Your refund will be reversed (1 credit).</p>
            </div>
            <button
              onclick={resumeJob}
              disabled={isResuming}
              class="btn-primary flex items-center gap-2"
            >
              <RotateCw class="w-4 h-4 {isResuming ? 'animate-spin' : ''}" />
              {isResuming ? 'Resuming...' : 'Resume'}
            </button>
          </div>
          {#if resumeError}
            <p class="mt-3 text-sm text-error">{resumeError}</p>
          {/if}
        </div>
      {/if}

      <!-- Stage List -->
      <div class="card mb-6 p-0 animate-fade-slide-in" style="animation-delay: 200ms;">
        <div class="px-6 py-4 border-b border-border">
          <h2 class="text-lg font-medium text-text-primary">Pipeline Stages</h2>
        </div>
        <ul class="divide-y divide-border">
          {#each displayStages as stage, index}
            <li
              class="px-6 py-4 flex items-center justify-between transition-colors hover:bg-bg-hover {stage.status === 'RUNNING' ? 'bg-info/5' : ''}"
              style="animation-delay: {250 + index * 50}ms;"
            >
              <div class="flex items-center gap-3">
                {#if stage.status === 'COMPLETED'}
                  <span class="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded-full bg-success/15 border border-success/20 text-success">
                    <CheckCircle class="w-4 h-4" />
                  </span>
                {:else if stage.status === 'RUNNING'}
                  <span class="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded-full bg-info/15 border border-info/20 text-info">
                    <Loader2 class="w-4 h-4 animate-spin" />
                  </span>
                {:else if stage.status === 'FAILED'}
                  <span class="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded-full bg-error/15 border border-error/20 text-error">
                    <XCircle class="w-4 h-4" />
                  </span>
                {:else if stage.status === 'SKIPPED'}
                  <span class="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded-full bg-bg-elevated border border-border text-text-muted">
                    <Minus class="w-4 h-4" />
                  </span>
                {:else}
                  <span class="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded-full bg-bg-elevated border border-border text-text-muted">
                    <span class="w-2 h-2 rounded-full bg-current opacity-50"></span>
                  </span>
                {/if}
                <span class="text-sm font-medium {stage.status === 'RUNNING' ? 'text-info' : stage.status === 'COMPLETED' ? 'text-text-primary' : 'text-text-secondary'}">
                  {stage.stageName}
                </span>
              </div>
              {#if stage.durationSeconds}
                <span class="text-sm text-text-muted font-mono">
                  {formatDuration(stage.durationSeconds)}
                </span>
              {/if}
            </li>
          {/each}
        </ul>
      </div>

      <!-- Results Section -->
      {@const reportAsset = job.assets.find(a => a.type === 'REPORT_JSON')}
      {@const landingAsset = job.assets.find(a => a.type === 'LANDING_PAGE')}

      {#if reportAsset || landingAsset}
        <div class="card p-6 animate-fade-slide-in" style="animation-delay: 300ms;">
          <h2 class="text-lg font-medium text-text-primary mb-4">Your Results</h2>
          <div class="flex flex-wrap gap-4">
            {#if reportAsset}
              <div class="flex flex-col items-start">
                <a
                  href="/jobs/{job.id}/report"
                  class="btn-primary"
                >
                  <FileText class="w-5 h-5" />
                  View Report
                </a>
                <a
                  href={reportAsset.url}
                  class="mt-2 text-xs text-text-muted hover:text-text-secondary transition-colors"
                  download
                >
                  Download JSON
                </a>
              </div>
            {/if}

            {#if landingAsset}
              <div class="flex flex-col items-start">
                <a
                  href={landingAsset.url}
                  target="_blank"
                  class="btn-secondary"
                >
                  <ExternalLink class="w-5 h-5" />
                  View Landing Page
                </a>
                <a
                  href="{landingAsset.url}?download=true"
                  class="mt-2 text-xs text-text-muted hover:text-text-secondary transition-colors"
                  download
                >
                  Download HTML
                </a>
              </div>
            {:else if job.landingPageStatus === 'RUNNING' || job.landingPageStatus === 'QUEUED'}
              <div class="flex items-center gap-2 text-sm text-info">
                <Loader2 class="w-4 h-4 animate-spin" />
                <span>Landing page is being generated...</span>
              </div>
            {:else if job.landingPageStatus === 'FAILED'}
              <div class="flex flex-col items-start gap-2">
                <div class="flex items-center gap-2 text-sm text-error">
                  <XCircle class="w-4 h-4" />
                  <span>Landing page generation failed</span>
                </div>
                <button
                  onclick={generateLanding}
                  disabled={generatingLanding}
                  class="btn-secondary btn-sm"
                >
                  {#if generatingLanding}
                    <Loader2 class="w-4 h-4 animate-spin" />
                    Retrying...
                  {:else}
                    <RotateCw class="w-4 h-4" />
                    Retry Landing Page
                  {/if}
                </button>
              </div>
            {:else if job.status === 'COMPLETED' && reportAsset && !job.progress.some(s => s.stageNumber === 11)}
              <div class="flex flex-col items-start gap-1">
                <button
                  onclick={generateLanding}
                  disabled={generatingLanding}
                  class="btn-secondary"
                >
                  {#if generatingLanding}
                    <Loader2 class="w-4 h-4 animate-spin" />
                    Generating...
                  {:else}
                    <Globe class="w-5 h-5" />
                    Generate Landing Page
                  {/if}
                </button>
                <span class="text-xs text-text-muted">Free - included with your research</span>
              </div>
            {/if}
          </div>
          {#if landingError}
            <p class="mt-3 text-sm text-error">{landingError}</p>
          {/if}
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
