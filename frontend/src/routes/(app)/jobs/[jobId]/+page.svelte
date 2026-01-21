<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { page } from '$app/stores';
  import { SSE_BASE } from '$lib/api';
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
    RotateCw
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
  }

  let job = $state<Job | null>(null);
  let loading = $state(true);
  let error = $state('');
  let eventSource: EventSource | null = null;
  let cancelling = $state(false);
  let cancelError = $state('');
  let isResuming = $state(false);
  let resumeError = $state('');

  const jobId = $derived($page.params.jobId);

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
      // Reset any FAILED stages to PENDING for proper visual feedback
      const updatedProgress = job.progress.map(stage =>
        stage.status === 'FAILED' ? { ...stage, status: 'PENDING' as const } : stage
      );
      job = { ...job, status: 'QUEUED', errorMessage: null, progress: updatedProgress };

      // Reconnect SSE for real-time updates
      eventSource?.close();
      eventSource = new EventSource(`${SSE_BASE}/jobs/${jobId}/events`);

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data && data.id) {
            job = data;
          }
        } catch (e) {
          console.error('Failed to parse SSE data:', e);
        }
      };

      eventSource.onerror = () => {
        eventSource?.close();
      };
    } catch (e) {
      resumeError = e instanceof Error ? e.message : 'Failed to resume job';
    } finally {
      isResuming = false;
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
      eventSource?.close();
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

    // SSE for real-time updates if job is still in progress
    if (job && !['COMPLETED', 'FAILED', 'CANCELLED'].includes(job.status)) {
      eventSource = new EventSource(`${SSE_BASE}/jobs/${jobId}/events`);

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data && data.id) {
            job = data;
          }
        } catch (e) {
          console.error('Failed to parse SSE data:', e);
        }
      };

      eventSource.onerror = () => {
        // Connection closed, likely job completed
        eventSource?.close();
      };
    }
  });

  onDestroy(() => {
    eventSource?.close();
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
        <div class="card p-6 mb-6 animate-fade-slide-in" style="animation-delay: 100ms;">
          <div class="flex justify-between items-center mb-3">
            <span class="text-sm font-medium text-text-secondary">
              {job.currentStageName || 'Initializing...'}
            </span>
            <span class="text-sm font-semibold text-accent">
              {Math.round(job.progressPercent)}%
            </span>
          </div>
          <div class="progress-bar h-3">
            <div
              class="progress-bar-fill {job.status === 'RUNNING' ? 'animate-shimmer' : ''}"
              style="width: {job.progressPercent}%"
            ></div>
          </div>
          <p class="mt-3 text-sm text-text-muted">
            {job.stagesCompleted} of {job.totalStages} stages completed
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

      <!-- Error Message (only show for permanently failed jobs) -->
      {#if job.errorMessage && job.status === 'FAILED'}
        <div class="p-4 rounded-lg bg-error/5 border border-error/20 mb-6 animate-fade-slide-in" style="animation-delay: 150ms;">
          <div class="flex items-start gap-3">
            <div class="p-2 rounded-lg bg-error/10 shrink-0">
              <XCircle class="w-5 h-5 text-error" />
            </div>
            <div class="flex-1">
              <h3 class="text-sm font-medium text-error">Error</h3>
              <p class="mt-1 text-sm text-error/80">{job.errorMessage}</p>
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
          {#each job.progress as stage, index}
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

      <!-- Download Links -->
      {#if job.status === 'COMPLETED' && job.assets.length > 0}
        <div class="card p-6 animate-fade-slide-in" style="animation-delay: 300ms;">
          <h2 class="text-lg font-medium text-text-primary mb-4">Your Results</h2>
          <div class="flex flex-wrap gap-4">
            {#each job.assets as asset}
              {#if asset.type === 'REPORT_JSON'}
                <div class="flex flex-col items-start">
                  <a
                    href="/jobs/{job.id}/report"
                    class="btn-primary"
                  >
                    <FileText class="w-5 h-5" />
                    View Report
                  </a>
                  <a
                    href={asset.url}
                    class="mt-2 text-xs text-text-muted hover:text-text-secondary transition-colors"
                    download
                  >
                    Download JSON
                  </a>
                </div>
              {:else if asset.type === 'LANDING_PAGE'}
                <div class="flex flex-col items-start">
                  <a
                    href={asset.url}
                    target="_blank"
                    class="btn-secondary"
                  >
                    <ExternalLink class="w-5 h-5" />
                    View Landing Page
                  </a>
                  <a
                    href="{asset.url}?download=true"
                    class="mt-2 text-xs text-text-muted hover:text-text-secondary transition-colors"
                    download
                  >
                    Download HTML
                  </a>
                </div>
              {/if}
            {/each}
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
