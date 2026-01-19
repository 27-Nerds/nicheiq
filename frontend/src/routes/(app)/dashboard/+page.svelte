<script lang="ts">
  import { page } from '$app/stores';
  import { onDestroy } from 'svelte';
  import { browser } from '$app/environment';
  import {
    Plus,
    Clock,
    CheckCircle,
    XCircle,
    Loader2,
    ArrowRight,
    Search,
    ExternalLink,
    Activity,
    RotateCcw,
    ChevronDown,
    ChevronUp,
    Globe,
    Sparkles,
    X
  } from 'lucide-svelte';

  interface Job {
    id: string;
    niche: string;
    status: string;
    currentStage: number;
    currentStageName: string | null;
    stagesCompleted: number;
    totalStages: number;
    progressPercent: number;
    errorMessage: string | null;
    createdAt: string;
    startedAt: string | null;
    completedAt: string | null;
    hasReport: boolean;
    hasLandingPage: boolean;
    // Queue position info (for QUEUED jobs)
    queuePosition?: number | null;
    aheadCount?: number;
    totalQueued?: number;
  }

  const TOTAL_STAGES = 16; // Fallback - actual value comes from job.totalStages

  let { data } = $props();

  const session = $derived($page.data.session);
  const initialJobs = $derived(data.jobs as Job[]);

  // Track SSE connections and live job updates
  let eventSources = $state<Map<string, EventSource>>(new Map());
  let jobUpdates = $state<Map<string, Job>>(new Map());

  // Merge initial jobs with live updates and sort by priority
  const jobs = $derived(
    initialJobs
      .map(job => jobUpdates.get(job.id) || job)
      .sort((a, b) => {
        // Priority: Running > Pending/Queued > Failed > Completed
        const statusPriority: Record<string, number> = {
          'RUNNING': 0,
          'PENDING': 1,
          'QUEUED': 1,
          'FAILED': 2,
          'COMPLETED': 3
        };
        const priorityA = statusPriority[a.status.toUpperCase()] ?? 4;
        const priorityB = statusPriority[b.status.toUpperCase()] ?? 4;

        if (priorityA !== priorityB) return priorityA - priorityB;

        // Within same priority, sort by date (newest first)
        return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
      })
  );

  // Stats counts
  const completedCount = $derived(jobs.filter((j) => j.status.toUpperCase() === 'COMPLETED').length);
  const inProgressCount = $derived(jobs.filter((j) => ['RUNNING', 'PENDING', 'QUEUED'].includes(j.status.toUpperCase())).length);
  const failedCount = $derived(jobs.filter((j) => j.status.toUpperCase() === 'FAILED').length);

  // Group jobs by category for visual separation
  const activeJobs = $derived(jobs.filter((j) => ['RUNNING', 'PENDING', 'QUEUED'].includes(j.status.toUpperCase())));
  const completedJobs = $derived(jobs.filter((j) => j.status.toUpperCase() === 'COMPLETED'));
  const failedJobs = $derived(jobs.filter((j) => j.status.toUpperCase() === 'FAILED'));

  // Collapsible state for completed jobs
  const INITIAL_VISIBLE_COMPLETED = 3;
  let showAllCompleted = $state(false);
  const visibleCompletedJobs = $derived(
    showAllCompleted ? completedJobs : completedJobs.slice(0, INITIAL_VISIBLE_COMPLETED)
  );
  const hasMoreCompleted = $derived(completedJobs.length > INITIAL_VISIBLE_COMPLETED);

  // Search/filter state
  let searchQuery = $state('');
  const filteredActiveJobs = $derived(
    searchQuery.trim()
      ? activeJobs.filter(j => j.niche.toLowerCase().includes(searchQuery.toLowerCase()))
      : activeJobs
  );
  const filteredFailedJobs = $derived(
    searchQuery.trim()
      ? failedJobs.filter(j => j.niche.toLowerCase().includes(searchQuery.toLowerCase()))
      : failedJobs
  );
  const filteredCompletedJobs = $derived(
    searchQuery.trim()
      ? completedJobs.filter(j => j.niche.toLowerCase().includes(searchQuery.toLowerCase()))
      : completedJobs
  );
  const filteredVisibleCompleted = $derived(
    showAllCompleted ? filteredCompletedJobs : filteredCompletedJobs.slice(0, INITIAL_VISIBLE_COMPLETED)
  );
  const hasFilteredResults = $derived(
    filteredActiveJobs.length > 0 || filteredFailedJobs.length > 0 || filteredCompletedJobs.length > 0
  );

  // Dismissable tip banner
  const TIP_DISMISSED_KEY = 'nicheiq_tip_dismissed';
  let tipDismissed = $state(browser ? localStorage.getItem(TIP_DISMISSED_KEY) === 'true' : false);

  function dismissTip() {
    tipDismissed = true;
    if (browser) {
      localStorage.setItem(TIP_DISMISSED_KEY, 'true');
    }
  }

  // Search input ref for keyboard shortcut
  let searchInput: HTMLInputElement;

  // Total filtered count for search results indicator
  const totalFilteredCount = $derived(
    filteredActiveJobs.length + filteredFailedJobs.length + filteredCompletedJobs.length
  );

  // Get effective job data (live update or initial)
  function getJobData(jobId: string): Job | undefined {
    return jobUpdates.get(jobId) || initialJobs.find(j => j.id === jobId);
  }

  // Connect SSE for active jobs (including queued to catch status changes)
  $effect(() => {
    const activeJobs = initialJobs.filter(j =>
      ['RUNNING', 'PENDING', 'QUEUED'].includes(j.status.toUpperCase())
    );

    // Connect to SSE for each active job
    for (const job of activeJobs) {
      if (!eventSources.has(job.id)) {
        const es = new EventSource(`/api/jobs/${job.id}/events`);

        es.onmessage = (e) => {
          try {
            const data = JSON.parse(e.data);
            jobUpdates.set(job.id, data);

            // Close connection if job completed/failed
            if (['COMPLETED', 'FAILED', 'CANCELLED'].includes(data.status?.toUpperCase())) {
              es.close();
              eventSources.delete(job.id);
            }
          } catch (err) {
            console.error('SSE parse error:', err);
          }
        };

        es.onerror = () => {
          es.close();
          eventSources.delete(job.id);
        };

        eventSources.set(job.id, es);
      }
    }

    // Cleanup connections for jobs no longer active
    for (const [jobId, es] of eventSources) {
      const job = getJobData(jobId);
      if (!job || ['COMPLETED', 'FAILED', 'CANCELLED'].includes(job.status.toUpperCase())) {
        es.close();
        eventSources.delete(jobId);
      }
    }
  });

  // Cleanup on destroy
  onDestroy(() => {
    eventSources.forEach(es => es.close());
    eventSources.clear();
  });

  function getStatusBadge(status: string) {
    switch (status.toUpperCase()) {
      case 'COMPLETED':
        return { class: 'badge-success', icon: CheckCircle, text: 'Completed', borderClass: 'border-l-success' };
      case 'RUNNING':
        return { class: 'badge-warning', icon: Loader2, text: 'Running', borderClass: 'border-l-warning' };
      case 'PENDING':
      case 'QUEUED':
        return { class: 'badge-info', icon: Clock, text: 'Queued', borderClass: 'border-l-secondary' };
      case 'FAILED':
        return { class: 'badge-error', icon: XCircle, text: 'Failed', borderClass: 'border-l-error' };
      default:
        return { class: 'badge-muted', icon: Clock, text: status, borderClass: 'border-l-border' };
    }
  }

  // Capitalize first letter of each word for professional titles
  function formatNicheTitle(niche: string): string {
    return niche
      .split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(' ');
  }

  function formatDate(dateStr: string) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  function formatElapsedTime(startedAt: string | null): string {
    if (!startedAt) return '';
    const start = new Date(startedAt);
    const now = new Date();
    const diffMs = now.getTime() - start.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'just started';
    if (diffMins === 1) return '1 min elapsed';
    return `${diffMins} min elapsed`;
  }

  // Retry a failed job
  let retryingJobs = $state<Set<string>>(new Set());

  async function retryJob(job: Job) {
    if (retryingJobs.has(job.id)) return;

    retryingJobs.add(job.id);
    try {
      const res = await fetch('/api/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ niche: job.niche }),
      });

      if (res.ok) {
        const data = await res.json();
        window.location.href = `/jobs/${data.id}`;
      }
    } catch (err) {
      console.error('Retry failed:', err);
    } finally {
      retryingJobs.delete(job.id);
    }
  }

  // Professional relative time formatting
  function formatRelativeDate(dateStr: string): string {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays}d ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;

    // For older dates, show formatted date
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined
    });
  }
</script>

<svelte:head>
  <title>Dashboard - NicheIQ</title>
</svelte:head>

<!-- Keyboard shortcut for search -->
<svelte:window onkeydown={(e) => {
  if (e.key === '/' && document.activeElement?.tagName !== 'INPUT' && document.activeElement?.tagName !== 'TEXTAREA') {
    e.preventDefault();
    searchInput?.focus();
  }
  if (e.key === 'Escape' && document.activeElement === searchInput) {
    searchInput?.blur();
    searchQuery = '';
  }
}} />

<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
  <!-- Header -->
  <div class="mb-8">
    <div class="flex items-center justify-between flex-wrap gap-4">
      <div>
        <div class="flex items-center gap-3 mb-1">
          <h1 class="text-2xl font-bold text-text-primary">
            Welcome back{session?.user?.name ? `, ${session.user.name}` : ''}
          </h1>
          {#if inProgressCount > 0}
            <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-warning/10 text-warning border border-warning/20 animate-pulse">
              <span class="w-1.5 h-1.5 rounded-full bg-warning"></span>
              {inProgressCount} active
            </span>
          {/if}
        </div>
        <p class="text-text-muted">
          Manage your market research reports
        </p>
      </div>
      {#if jobs.length > 0 && inProgressCount === 0}
        <a
          href="/jobs/new"
          class="btn-primary hidden sm:inline-flex"
        >
          <Plus class="w-4 h-4" />
          New Research
        </a>
      {/if}
    </div>
  </div>

  <!-- Pro tip banner (show when no active jobs and has completed jobs, unless dismissed) -->
  {#if jobs.length > 0 && inProgressCount === 0 && completedCount > 0 && !tipDismissed}
    <div class="mb-6 p-4 rounded-lg bg-gradient-to-r from-accent/5 via-secondary/5 to-accent/5 border border-accent/10 animate-fade-slide-in">
      <div class="flex items-center justify-between gap-3">
        <div class="flex items-center gap-3">
          <div class="p-2 rounded-lg bg-accent/10">
            <Sparkles class="w-4 h-4 text-accent" />
          </div>
          <p class="text-sm text-text-secondary">
            <span class="font-medium text-text-primary">Ready for more insights?</span>
            {' '}Start another research to explore new market opportunities.
          </p>
        </div>
        <button
          onclick={dismissTip}
          class="p-1 rounded hover:bg-bg-hover text-text-muted hover:text-text-primary transition-colors shrink-0"
          title="Dismiss"
        >
          <X class="w-4 h-4" />
        </button>
      </div>
    </div>
  {/if}

  <!-- Stats Overview -->
  <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
    <div class="card hover:shadow-md hover:border-accent/30 transition-all duration-200 cursor-default">
      <div class="flex items-center gap-3">
        <div class="p-2.5 rounded-xl bg-accent/8 border border-accent/15">
          <svg class="w-5 h-5 text-accent" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 7V17C3 18.1046 3.89543 19 5 19H19C20.1046 19 21 18.1046 21 17V9C21 7.89543 20.1046 7 19 7H13L11 5H5C3.89543 5 3 5.89543 3 7Z" />
            <path d="M8 13H16" />
            <path d="M8 16H13" />
          </svg>
        </div>
        <div>
          <p class="text-2xl font-bold text-text-primary">{jobs.length}</p>
          <p class="text-sm text-text-muted">Total</p>
        </div>
      </div>
    </div>
    <div class="card hover:shadow-md hover:border-emerald-500/30 transition-all duration-200 cursor-default">
      <div class="flex items-center gap-3">
        <div class="p-2.5 rounded-xl bg-emerald-500/8 border border-emerald-500/15">
          <svg class="w-5 h-5 text-emerald-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 22C12 22 20 18 20 12V5L12 2L4 5V12C4 18 12 22 12 22Z" />
            <path d="M9 12L11 14L15 10" />
          </svg>
        </div>
        <div>
          <p class="text-2xl font-bold text-text-primary">{completedCount}</p>
          <p class="text-sm text-text-muted">Completed</p>
        </div>
      </div>
    </div>
    <div class="card hover:shadow-md hover:border-amber-500/30 transition-all duration-200 cursor-default">
      <div class="flex items-center gap-3">
        <div class="p-2.5 rounded-xl bg-amber-500/8 border border-amber-500/15">
          <svg class="w-5 h-5 text-amber-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 12C21 16.9706 16.9706 21 12 21C7.02944 21 3 16.9706 3 12C3 7.02944 7.02944 3 12 3C14.8273 3 17.35 4.30367 19 6.34267" />
            <path d="M21 3V9H15" />
          </svg>
        </div>
        <div>
          <p class="text-2xl font-bold text-text-primary">{inProgressCount}</p>
          <p class="text-sm text-text-muted">In Progress</p>
        </div>
      </div>
    </div>
  </div>

  <!-- Search bar (only show when there are jobs) -->
  {#if jobs.length > 0}
    <div class="mb-6 flex flex-col sm:flex-row sm:items-center gap-3">
      <div class="relative">
        <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
        <input
          type="text"
          bind:this={searchInput}
          bind:value={searchQuery}
          placeholder="Search research by niche..."
          class="input pl-10 pr-20 w-full sm:w-80"
        />
        <div class="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-2">
          {#if searchQuery}
            <button
              onclick={() => searchQuery = ''}
              class="text-text-muted hover:text-text-primary transition-colors"
            >
              <XCircle class="w-4 h-4" />
            </button>
          {:else}
            <kbd class="hidden sm:inline-flex items-center px-1.5 py-0.5 text-xs font-mono text-text-muted bg-bg-surface border border-border rounded">/</kbd>
          {/if}
        </div>
      </div>
      {#if searchQuery}
        <p class="text-sm text-text-muted">
          {totalFilteredCount} {totalFilteredCount === 1 ? 'result' : 'results'}
        </p>
      {/if}
    </div>
  {/if}

  <!-- Job List -->
  {#if jobs.length === 0}
    <div class="relative overflow-hidden rounded-xl border border-border bg-gradient-to-br from-bg-surface via-bg-elevated to-accent/5 text-center py-16 px-6">
      <!-- Decorative elements -->
      <div class="absolute top-0 right-0 w-64 h-64 bg-accent/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2"></div>
      <div class="absolute bottom-0 left-0 w-48 h-48 bg-secondary/5 rounded-full blur-3xl translate-y-1/2 -translate-x-1/2"></div>

      <div class="relative">
        <div class="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-accent/20 to-accent/5 border border-accent/20 flex items-center justify-center shadow-lg">
          <Search class="w-10 h-10 text-accent" />
        </div>
        <h2 class="text-2xl font-bold text-text-primary mb-3">
          Ready to validate your next idea?
        </h2>
        <p class="text-text-secondary mb-8 max-w-lg mx-auto leading-relaxed">
          NicheIQ analyzes Reddit discussions, identifies pain points, and generates a comprehensive market research report in minutes.
        </p>
        <a href="/jobs/new" class="btn-primary inline-flex text-base px-6 py-3">
          <Plus class="w-5 h-5" />
          Start Your First Research
        </a>
        <p class="text-xs text-text-muted mt-4">
          Average research takes 5-10 minutes to complete
        </p>
      </div>
    </div>
  {:else}
    <!-- No search results -->
    {#if searchQuery && !hasFilteredResults}
      <div class="card text-center py-12">
        <Search class="w-12 h-12 mx-auto mb-4 text-text-muted" />
        <h3 class="text-lg font-semibold text-text-primary mb-2">No results found</h3>
        <p class="text-text-muted mb-4">No research matches "{searchQuery}"</p>
        <button
          onclick={() => searchQuery = ''}
          class="btn-secondary inline-flex"
        >
          Clear search
        </button>
      </div>
    {:else}
    <div class="space-y-6">
      <!-- Active Jobs Section -->
      {#if filteredActiveJobs.length > 0}
        <div class="space-y-4">
          <h2 class="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-warning/5 border border-warning/10">
            <Activity class="w-4 h-4 text-warning" />
            <span class="text-sm font-semibold text-text-primary">In Progress</span>
            <span class="text-xs font-medium text-warning bg-warning/10 px-1.5 py-0.5 rounded">{filteredActiveJobs.length}</span>
          </h2>
          <div class="grid gap-4">
            {#each filteredActiveJobs as job, i}
              {@const statusBadge = getStatusBadge(job.status)}
              {@const StatusIcon = statusBadge.icon}
              {@const isRunning = job.status.toUpperCase() === 'RUNNING'}
              {@const isPending = job.status.toUpperCase() === 'PENDING'}
              {@const isQueued = job.status.toUpperCase() === 'QUEUED'}
              {@const totalStages = job.totalStages || TOTAL_STAGES}
              <div
                class="card hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200 border-l-4 animate-fade-slide-in {statusBadge.borderClass}"
                style="animation-delay: {i * 50}ms"
              >
                <div class="flex flex-col sm:flex-row sm:items-start gap-4">
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-3 mb-2">
                      <h3 class="text-lg font-semibold text-text-primary truncate">
                        {formatNicheTitle(job.niche)}
                      </h3>
                      <span class="badge {statusBadge.class} flex items-center gap-1.5 shrink-0">
                        <StatusIcon class="w-3 h-3 {isRunning ? 'animate-spin' : ''}" />
                        {statusBadge.text}
                      </span>
                    </div>
                    {#if isRunning && job.currentStageName}
                      <div class="flex items-center gap-2 mb-3">
                        <Activity class="w-4 h-4 text-accent" />
                        <span class="text-sm text-accent font-medium">
                          {job.currentStageName}
                        </span>
                      </div>
                    {:else if isQueued || isPending}
                      <p class="text-sm text-text-muted mb-3">
                        {#if job.queuePosition === 1}
                          <span class="text-accent font-medium">Next in queue</span>
                        {:else if job.queuePosition && job.aheadCount}
                          <span class="font-medium">{job.aheadCount} {job.aheadCount === 1 ? 'report' : 'reports'} ahead</span>
                          <span class="text-text-muted/70"> &middot; Position {job.queuePosition}</span>
                        {:else}
                          <span class="italic">Waiting to start...</span>
                        {/if}
                      </p>
                    {/if}
                    {#if isRunning && job.progressPercent > 0}
                      <div class="mb-3">
                        <div class="progress-bar">
                          <div class="progress-bar-fill animate-shimmer" style="width: {job.progressPercent}%"></div>
                        </div>
                        <p class="text-xs text-text-muted mt-1">{job.stagesCompleted} of {totalStages} stages completed</p>
                      </div>
                    {/if}
                    <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-text-muted">
                      <span class="flex items-center gap-1" title={formatDate(job.createdAt)}>
                        <Clock class="w-3.5 h-3.5" />
                        {formatRelativeDate(job.createdAt)}
                      </span>
                      {#if isRunning && job.startedAt}
                        <span class="text-accent font-medium">{formatElapsedTime(job.startedAt)}</span>
                      {/if}
                    </div>
                  </div>
                  <div class="flex items-center gap-3 shrink-0">
                    <a href="/jobs/{job.id}" class="btn-secondary">
                      {isRunning ? 'View Progress' : 'View Status'}
                      <ArrowRight class="w-4 h-4" />
                    </a>
                  </div>
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/if}

      <!-- Failed Jobs Section -->
      {#if filteredFailedJobs.length > 0}
        {#if filteredActiveJobs.length > 0}
          <div class="border-t border-border/50 pt-2"></div>
        {/if}
        <div class="space-y-4">
          <h2 class="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-error/5 border border-error/10">
            <XCircle class="w-4 h-4 text-error" />
            <span class="text-sm font-semibold text-text-primary">Failed</span>
            <span class="text-xs font-medium text-error bg-error/10 px-1.5 py-0.5 rounded">{filteredFailedJobs.length}</span>
          </h2>
          <div class="grid gap-4">
            {#each filteredFailedJobs as job, i}
              {@const statusBadge = getStatusBadge(job.status)}
              {@const StatusIcon = statusBadge.icon}
              <div
                class="card hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200 border-l-4 animate-fade-slide-in {statusBadge.borderClass}"
                style="animation-delay: {i * 50}ms"
              >
                <div class="flex flex-col sm:flex-row sm:items-start gap-4">
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-3 mb-2">
                      <h3 class="text-lg font-semibold text-text-primary truncate">
                        {formatNicheTitle(job.niche)}
                      </h3>
                      <span class="badge {statusBadge.class} flex items-center gap-1.5 shrink-0">
                        <StatusIcon class="w-3 h-3" />
                        {statusBadge.text}
                      </span>
                    </div>
                    <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-text-muted">
                      <span class="flex items-center gap-1" title={formatDate(job.createdAt)}>
                        <Clock class="w-3.5 h-3.5" />
                        {formatRelativeDate(job.createdAt)}
                      </span>
                      {#if job.errorMessage && job.status.toUpperCase() === 'FAILED'}
                        <span class="text-error truncate max-w-xs" title={job.errorMessage}>{job.errorMessage}</span>
                      {/if}
                    </div>
                  </div>
                  <div class="flex items-center gap-2 shrink-0">
                    <button
                      onclick={() => retryJob(job)}
                      disabled={retryingJobs.has(job.id)}
                      class="btn-primary flex items-center gap-2"
                      title="Start a new research with the same niche"
                    >
                      <RotateCcw class="w-4 h-4 {retryingJobs.has(job.id) ? 'animate-spin' : ''}" />
                      {retryingJobs.has(job.id) ? 'Retrying...' : 'Retry'}
                    </button>
                    <a href="/jobs/{job.id}" class="btn-secondary text-error border-error/30 hover:border-error hover:bg-error/5">
                      Details
                      <ArrowRight class="w-4 h-4" />
                    </a>
                  </div>
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/if}

      <!-- Completed Jobs Section -->
      {#if filteredCompletedJobs.length > 0}
        {#if filteredActiveJobs.length > 0 || filteredFailedJobs.length > 0}
          <div class="border-t border-border/50 pt-2"></div>
        {/if}
        <div class="space-y-4">
          <h2 class="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-success/5 border border-success/10">
            <CheckCircle class="w-4 h-4 text-success" />
            <span class="text-sm font-semibold text-text-primary">Completed</span>
            <span class="text-xs font-medium text-success bg-success/10 px-1.5 py-0.5 rounded">{filteredCompletedJobs.length}</span>
          </h2>
          <div class="grid gap-4">
            {#each filteredVisibleCompleted as job, i}
              {@const statusBadge = getStatusBadge(job.status)}
              {@const StatusIcon = statusBadge.icon}
              <div
                class="card hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200 border-l-4 animate-fade-slide-in {statusBadge.borderClass}"
                style="animation-delay: {i * 50}ms"
              >
                <div class="flex flex-col sm:flex-row sm:items-start gap-4">
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-3 mb-2">
                      <h3 class="text-lg font-semibold text-text-primary truncate">
                        {formatNicheTitle(job.niche)}
                      </h3>
                      <span class="badge {statusBadge.class} flex items-center gap-1.5 shrink-0">
                        <StatusIcon class="w-3 h-3" />
                        {statusBadge.text}
                      </span>
                      {#if job.hasLandingPage}
                        <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs bg-secondary/10 text-secondary border border-secondary/20" title="Landing page available">
                          <Globe class="w-3 h-3" />
                        </span>
                      {/if}
                    </div>
                    <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-text-muted">
                      <span class="flex items-center gap-1" title={formatDate(job.createdAt)}>
                        <Clock class="w-3.5 h-3.5" />
                        {formatRelativeDate(job.createdAt)}
                      </span>
                      {#if job.completedAt}
                        <span class="text-success">
                          Completed {formatRelativeDate(job.completedAt)}
                        </span>
                      {/if}
                    </div>
                  </div>
                  <div class="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 shrink-0 w-full sm:w-auto">
                    <!-- Report actions -->
                    <div class="flex flex-col items-center">
                      <a href="/jobs/{job.id}/report" class="btn-primary justify-center w-full">
                        View Report
                        <ArrowRight class="w-4 h-4" />
                      </a>
                      <a
                        href="/api/jobs/{job.id}/reportjson"
                        download
                        class="mt-1.5 text-xs text-text-muted hover:text-text-secondary transition-colors"
                      >
                        Download JSON
                      </a>
                    </div>
                    <!-- Landing page actions -->
                    {#if job.hasLandingPage}
                      <div class="flex flex-col items-center">
                        <a
                          href="/api/jobs/{job.id}/landingpage"
                          target="_blank"
                          rel="noopener noreferrer"
                          class="btn-secondary justify-center w-full"
                        >
                          Landing Page
                          <ExternalLink class="w-4 h-4" />
                        </a>
                        <a
                          href="/api/jobs/{job.id}/landingpage?download=true"
                          download
                          class="mt-1.5 text-xs text-text-muted hover:text-text-secondary transition-colors"
                        >
                          Download HTML
                        </a>
                      </div>
                    {/if}
                  </div>
                </div>
              </div>
            {/each}
          </div>

          <!-- Show more/less button -->
          {#if filteredCompletedJobs.length > INITIAL_VISIBLE_COMPLETED}
            <button
              onclick={() => showAllCompleted = !showAllCompleted}
              class="w-full py-3 px-4 rounded-lg border border-border bg-bg-surface hover:bg-bg-hover text-text-secondary hover:text-text-primary transition-colors flex items-center justify-center gap-2 text-sm font-medium"
            >
              {#if showAllCompleted}
                <ChevronUp class="w-4 h-4" />
                Show less
              {:else}
                <ChevronDown class="w-4 h-4" />
                Show {filteredCompletedJobs.length - INITIAL_VISIBLE_COMPLETED} more completed
              {/if}
            </button>
          {/if}
        </div>
      {/if}
    </div>
    {/if}
  {/if}
</div>
