<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { page } from '$app/stores';
  import { SSE_BASE } from '$lib/api';

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

  const jobId = $derived($page.params.jobId);

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

  function getStatusColor(status: string): string {
    switch (status) {
      case 'COMPLETED': return 'text-success';
      case 'RUNNING': return 'text-info';
      case 'FAILED': return 'text-error';
      case 'CANCELLED': return 'text-text-muted';
      default: return 'text-warning';
    }
  }

  function formatDuration(seconds: number | null): string {
    if (!seconds) return '';
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${mins}m ${secs}s`;
  }
</script>

<svelte:head>
  <title>{job ? `Job ${job.status}` : 'Loading...'} - NicheIQ</title>
</svelte:head>

<div class="py-8">
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
    {#if loading}
      <div class="text-center py-12">
        <svg class="animate-spin h-10 w-10 text-accent mx-auto" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <p class="mt-4 text-text-secondary">Loading job status...</p>
      </div>
    {:else if error}
      <div class="card p-8 text-center">
        <svg class="h-12 w-12 text-error mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <h2 class="mt-4 text-xl font-semibold text-text-primary">Error</h2>
        <p class="mt-2 text-text-secondary">{error}</p>
        <a href="/jobs/new" class="mt-6 btn-primary inline-block">Start New Research</a>
      </div>
    {:else if job}
      <!-- Header -->
      <div class="mb-8">
        <div class="flex items-center justify-between">
          <div>
            <h1 class="text-2xl font-bold text-text-primary">Research Progress</h1>
            <p class="mt-1 text-sm text-text-muted truncate max-w-xl" title={job.niche}>
              {job.niche.length > 100 ? job.niche.substring(0, 100) + '...' : job.niche}
            </p>
          </div>
          <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium {getStatusColor(job.status)} {job.status === 'COMPLETED' ? 'bg-success/20' : job.status === 'RUNNING' ? 'bg-info/20' : job.status === 'FAILED' ? 'bg-error/20' : 'bg-bg-elevated'}">
            {#if job.status === 'RUNNING'}
              <svg class="animate-spin -ml-1 mr-2 h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
            {/if}
            {job.status}
          </span>
        </div>
      </div>

      <!-- Queue Position (for QUEUED jobs) -->
      {#if job.status === 'QUEUED' || job.status === 'PENDING'}
        <div class="card p-6 mb-6 bg-warning/5 border-warning/20">
          <div class="flex items-center gap-4">
            <div class="p-3 rounded-full bg-warning/10">
              <svg class="w-6 h-6 text-warning" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <polyline points="12 6 12 12 16 14"></polyline>
              </svg>
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
        <div class="card p-6 mb-6">
          <div class="flex justify-between items-center mb-2">
            <span class="text-sm font-medium text-text-secondary">
              {job.currentStageName || 'Initializing...'}
            </span>
            <span class="text-sm font-semibold text-accent">
              {Math.round(job.progressPercent)}%
            </span>
          </div>
          <div class="w-full bg-bg-elevated rounded-full h-3 overflow-hidden">
            <div
              class="bg-accent h-3 rounded-full transition-all duration-500 ease-out"
              style="width: {job.progressPercent}%"
            ></div>
          </div>
          <p class="mt-2 text-sm text-text-muted">
            {job.stagesCompleted} of {job.totalStages} stages completed
          </p>
        </div>
      {/if}

      <!-- Error Message -->
      {#if job.errorMessage}
        <div class="rounded-lg bg-error/10 p-4 mb-6 border border-error/30">
          <div class="flex">
            <div class="flex-shrink-0">
              <svg class="h-5 w-5 text-error" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z" clip-rule="evenodd" />
              </svg>
            </div>
            <div class="ml-3">
              <h3 class="text-sm font-medium text-error">Error</h3>
              <p class="mt-1 text-sm text-error/80">{job.errorMessage}</p>
            </div>
          </div>
        </div>
      {/if}

      <!-- Stage List -->
      <div class="card mb-6">
        <div class="px-6 py-4 border-b border-border">
          <h2 class="text-lg font-medium text-text-primary">Pipeline Stages</h2>
        </div>
        <ul class="divide-y divide-border">
          {#each job.progress as stage}
            <li class="px-6 py-4 flex items-center justify-between {stage.status === 'RUNNING' ? 'bg-info/10' : ''}">
              <div class="flex items-center">
                {#if stage.status === 'COMPLETED'}
                  <span class="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full bg-success/20 text-success">
                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                      <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                    </svg>
                  </span>
                {:else if stage.status === 'RUNNING'}
                  <span class="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full bg-info/20 text-info">
                    <svg class="animate-spin w-4 h-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                  </span>
                {:else if stage.status === 'FAILED'}
                  <span class="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full bg-error/20 text-error">
                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                      <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
                    </svg>
                  </span>
                {:else if stage.status === 'SKIPPED'}
                  <span class="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full bg-bg-elevated text-text-muted">
                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                      <path fill-rule="evenodd" d="M3 10a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clip-rule="evenodd" />
                    </svg>
                  </span>
                {:else}
                  <span class="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full bg-bg-elevated text-text-muted">
                    <span class="w-2 h-2 rounded-full bg-current"></span>
                  </span>
                {/if}
                <span class="ml-3 text-sm font-medium {stage.status === 'RUNNING' ? 'text-info' : 'text-text-primary'}">
                  {stage.stageName}
                </span>
              </div>
              {#if stage.durationSeconds}
                <span class="text-sm text-text-muted">
                  {formatDuration(stage.durationSeconds)}
                </span>
              {/if}
            </li>
          {/each}
        </ul>
      </div>

      <!-- Download Links -->
      {#if job.status === 'COMPLETED' && job.assets.length > 0}
        <div class="card p-6">
          <h2 class="text-lg font-medium text-text-primary mb-4">Your Results</h2>
          <div class="flex flex-wrap gap-6">
            {#each job.assets as asset}
              {#if asset.type === 'REPORT_JSON'}
                <div class="flex flex-col items-start">
                  <a
                    href="/jobs/{job.id}/report"
                    class="btn-primary inline-flex items-center"
                  >
                    <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
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
                    class="btn-secondary inline-flex items-center"
                  >
                    <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
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
      <div class="mt-6 text-center text-sm text-text-muted">
        <p>Job ID: {job.id}</p>
        {#if job.startedAt}
          <p>Started: {new Date(job.startedAt).toLocaleString()}</p>
        {/if}
        {#if job.completedAt}
          <p>Completed: {new Date(job.completedAt).toLocaleString()}</p>
        {/if}
      </div>
    {/if}
  </div>
</div>
