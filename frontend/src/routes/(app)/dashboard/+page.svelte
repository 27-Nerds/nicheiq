<script lang="ts">
  import { page } from '$app/stores';
  import { onDestroy, untrack } from 'svelte';
  import { browser } from '$app/environment';
  import { SvelteMap, SvelteSet } from 'svelte/reactivity';
  import { subscribeToProgress, isTerminalStatus } from '$lib/api';
  import {
    Plus,
    XCircle,
    Search,
    ChevronDown,
    ChevronUp,
    Sparkles,
    X,
    FolderOpen,
    ShieldCheck,
    RefreshCw
  } from 'lucide-svelte';
  import { showNewResearchModal } from '$lib/stores/newResearchModal';
  import JobCard from '$lib/components/ui/JobCard.svelte';

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
    creditRefunded?: boolean;
    // Queue position info (for QUEUED jobs)
    queuePosition?: number | null;
    aheadCount?: number;
    totalQueued?: number;
    // Quality gate stop metadata
    stopReason?: string | null;
    stopReasonDetails?: StopReasonDetails | null;
  }

  let { data } = $props();

  const session = $derived($page.data.session);
  const initialJobs = $derived(data.jobs as Job[]);

  // Track SSE subscriptions and live job updates
  // Use regular Map for sseUnsubscribers since it doesn't need to trigger reactive updates
  const sseUnsubscribers = new Map<string, () => void>();
  let jobUpdates = new SvelteMap<string, Job>();

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
  const INITIAL_VISIBLE_COMPLETED = 6;
  let showAllCompleted = $state(false);

  // Collapsible state for failed jobs
  let showFailedJobs = $state(true);
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
  let searchInput = $state<HTMLInputElement | null>(null);

  // Overflow menu state for completed job cards
  let openMenuId = $state<string | null>(null);

  function toggleMenu(jobId: string, event: MouseEvent) {
    event.stopPropagation();
    openMenuId = openMenuId === jobId ? null : jobId;
  }

  function closeMenu() {
    openMenuId = null;
  }

  // Total filtered count for search results indicator
  const totalFilteredCount = $derived(
    filteredActiveJobs.length + filteredFailedJobs.length + filteredCompletedJobs.length
  );

  // Get effective job data (live update or initial)
  function getJobData(jobId: string): Job | undefined {
    return jobUpdates.get(jobId) || initialJobs.find(j => j.id === jobId);
  }

  // Connect SSE for active jobs (including queued to catch status changes)
  // Use $effect.pre with untrack() to prevent reactive tracking of map mutations
  $effect.pre(() => {
    // Only track initialJobs for dependencies
    const activeJobsList = initialJobs.filter(j => !isTerminalStatus(j.status));

    // Use untrack to prevent tracking map mutations
    untrack(() => {
      // Connect to SSE for each active job
      for (const job of activeJobsList) {
        if (!sseUnsubscribers.has(job.id)) {
          const unsubscribe = subscribeToProgress(
            job.id,
            (data) => {
              jobUpdates.set(job.id, data as Job);

              // Cleanup subscription if job reached terminal state
              if (isTerminalStatus(data.status)) {
                sseUnsubscribers.get(job.id)?.();
                sseUnsubscribers.delete(job.id);
                // Prune completed job data after brief delay (allows final UI update)
                setTimeout(() => jobUpdates.delete(job.id), 5000);
              }
            },
            (err) => console.warn(`SSE error for job ${job.id}:`, err.message)
          );

          sseUnsubscribers.set(job.id, unsubscribe);
        }
      }

      // Cleanup subscriptions for jobs no longer active
      // Use initialJobs.find() instead of getJobData() to avoid reading jobUpdates
      for (const [jobId] of sseUnsubscribers) {
        const job = initialJobs.find(j => j.id === jobId);
        if (!job || isTerminalStatus(job.status)) {
          sseUnsubscribers.get(jobId)?.();
          sseUnsubscribers.delete(jobId);
        }
      }
    });
  });

  // Cleanup on destroy
  onDestroy(() => {
    sseUnsubscribers.forEach(unsubscribe => unsubscribe());
    sseUnsubscribers.clear();
  });

  // Resume a failed job from checkpoint (no credit charge)
  let resumingJobs = new SvelteSet<string>();

  async function resumeJob(job: Job) {
    if (resumingJobs.has(job.id)) return;

    resumingJobs.add(job.id);
    try {
      const res = await fetch(`/api/jobs/${job.id}/resume`, {
        method: 'POST',
      });

      if (res.ok) {
        // Redirect to job page to see progress
        window.location.href = `/jobs/${job.id}`;
      } else {
        const data = await res.json();
        console.error('Resume failed:', data.error || 'Unknown error');
      }
    } catch (err) {
      console.error('Resume failed:', err);
    } finally {
      resumingJobs.delete(job.id);
    }
  }

  // Cancel an active job
  let cancellingJobs = new SvelteSet<string>();

  async function cancelJob(job: Job) {
    if (cancellingJobs.has(job.id)) return;

    cancellingJobs.add(job.id);
    try {
      const res = await fetch(`/api/jobs/${job.id}/cancel`, {
        method: 'POST',
      });

      if (res.ok) {
        // Update local state to reflect cancellation
        jobUpdates.set(job.id, { ...job, status: 'CANCELLED', errorMessage: 'Cancelled by user' });

        // Close SSE connection for this job
        const unsubscribe = sseUnsubscribers.get(job.id);
        if (unsubscribe) {
          unsubscribe();
          sseUnsubscribers.delete(job.id);
        }
      }
    } catch (err) {
      console.error('Cancel failed:', err);
    } finally {
      cancellingJobs.delete(job.id);
    }
  }

</script>

<svelte:head>
  <title>Dashboard - NicheIQ</title>
</svelte:head>

<!-- Keyboard shortcut for search + close menus on outside click -->
<svelte:window
  onkeydown={(e) => {
    if (e.key === '/' && document.activeElement?.tagName !== 'INPUT' && document.activeElement?.tagName !== 'TEXTAREA') {
      e.preventDefault();
      searchInput?.focus();
    }
    if (e.key === 'Escape') {
      if (openMenuId) {
        closeMenu();
      } else if (document.activeElement === searchInput) {
        searchInput?.blur();
        searchQuery = '';
      }
    }
  }}
  onclick={(e) => {
    // Close overflow menu when clicking outside
    if (openMenuId) {
      const target = e.target as HTMLElement;
      if (!target.closest('[data-menu-container]')) {
        closeMenu();
      }
    }
  }}
/>

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
        <button
          onclick={() => ($showNewResearchModal = true)}
          class="btn-primary hidden sm:inline-flex"
        >
          <Plus class="w-4 h-4" />
          New Research
        </button>
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
    <div class="card hover:shadow-md hover:border-accent/30 transition-all duration-200 cursor-default border-l-4 border-l-accent">
      <div class="flex items-center gap-4">
        <div class="p-2.5 rounded-xl bg-accent/10 border border-accent/20">
          <FolderOpen class="w-5 h-5 text-accent" />
        </div>
        <div>
          <p class="text-4xl font-display font-bold text-text-primary tracking-tight">{jobs.length}</p>
          <p class="text-xs font-mono uppercase tracking-wider text-text-muted mt-1">Total Research</p>
        </div>
      </div>
    </div>
    <div class="card hover:shadow-md hover:border-success/30 transition-all duration-200 cursor-default border-l-4 border-l-success">
      <div class="flex items-center gap-4">
        <div class="p-2.5 rounded-xl bg-success/10 border border-success/20">
          <ShieldCheck class="w-5 h-5 text-success" />
        </div>
        <div>
          <p class="text-4xl font-display font-bold text-text-primary tracking-tight">{completedCount}</p>
          <p class="text-xs font-mono uppercase tracking-wider text-text-muted mt-1">Completed</p>
        </div>
      </div>
    </div>
    <div class="card hover:shadow-md hover:border-warning/30 transition-all duration-200 cursor-default border-l-4 border-l-warning">
      <div class="flex items-center gap-4">
        <div class="p-2.5 rounded-xl bg-warning/10 border border-warning/20">
          <RefreshCw class="w-5 h-5 text-warning" />
        </div>
        <div>
          <p class="text-4xl font-display font-bold text-text-primary tracking-tight">{inProgressCount}</p>
          <p class="text-xs font-mono uppercase tracking-wider text-text-muted mt-1">In Progress</p>
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
          placeholder="Search research..."
          class="input input-with-icon w-full sm:w-72"
        />
        <div class="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-2">
          {#if searchQuery}
            <button
              onclick={() => searchQuery = ''}
              aria-label="Clear search"
              class="text-text-muted hover:text-text-primary transition-colors"
            >
              <XCircle class="w-4 h-4" />
            </button>
          {:else}
            <kbd class="hidden sm:inline-flex items-center justify-center w-5 h-5 text-[10px] font-mono text-text-muted bg-bg-elevated border border-border rounded shadow-sm">/</kbd>
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
        <div class="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-accent/20 to-accent/5 border border-accent/20 flex items-center justify-center shadow-lg animate-float">
          <Search class="w-10 h-10 text-accent" />
        </div>
        <h2 class="text-2xl font-bold text-text-primary mb-3">
          Ready to validate your next idea?
        </h2>
        <p class="text-text-secondary mb-8 max-w-lg mx-auto leading-relaxed">
          NicheIQ analyzes Reddit discussions, identifies pain points, and generates a comprehensive market research report in minutes.
        </p>
        <button onclick={() => ($showNewResearchModal = true)} class="btn-primary inline-flex text-base px-6 py-3">
          <Plus class="w-5 h-5" />
          Start Your First Research
        </button>
        <p class="text-xs text-text-muted mt-4">
          Average research takes ~45 minutes to complete
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
          <div class="flex items-center gap-3">
            <div class="w-1 h-6 rounded-full bg-warning"></div>
            <h2 class="text-sm font-display font-semibold text-text-primary uppercase tracking-wide">
              In Progress
            </h2>
            <span class="text-xs font-mono text-warning bg-warning/10 px-2 py-0.5 rounded-full">
              {filteredActiveJobs.length}
            </span>
          </div>
          <div class="grid gap-3">
            {#each filteredActiveJobs as job, i}
              <JobCard
                {job}
                onCancel={cancelJob}
                isCancelling={cancellingJobs.has(job.id)}
                animationDelay={i * 50}
              />
            {/each}
          </div>
        </div>
      {/if}

      <!-- Completed Jobs Section -->
      {#if filteredCompletedJobs.length > 0}
        {#if filteredActiveJobs.length > 0}
          <div class="my-6">
            <div class="h-px bg-gradient-to-r from-transparent via-border-emphasis/50 to-transparent"></div>
          </div>
        {/if}
        <div class="space-y-4">
          <div class="flex items-center gap-3">
            <div class="w-1 h-6 rounded-full bg-success"></div>
            <h2 class="text-sm font-display font-semibold text-text-primary uppercase tracking-wide">
              Completed
            </h2>
            <span class="text-xs font-mono text-success bg-success/10 px-2 py-0.5 rounded-full">
              {filteredCompletedJobs.length}
            </span>
          </div>
          <div class="grid gap-3">
            {#each filteredVisibleCompleted as job, i}
              <JobCard
                {job}
                animationDelay={i * 50}
                isMenuOpen={openMenuId === job.id}
                onMenuToggle={toggleMenu}
              />
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

      <!-- Failed Jobs Section -->
      {#if filteredFailedJobs.length > 0}
        {#if filteredActiveJobs.length > 0 || filteredCompletedJobs.length > 0}
          <div class="my-6">
            <div class="h-px bg-gradient-to-r from-transparent via-border-emphasis/50 to-transparent"></div>
          </div>
        {/if}
        <div class="space-y-4">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <div class="w-1 h-6 rounded-full bg-error"></div>
              <h2 class="text-sm font-display font-semibold text-text-primary uppercase tracking-wide">
                Failed
              </h2>
              <span class="text-xs font-mono text-error bg-error/10 px-2 py-0.5 rounded-full">
                {filteredFailedJobs.length}
              </span>
            </div>
            <button
              onclick={() => showFailedJobs = !showFailedJobs}
              class="p-1.5 rounded-md text-text-muted hover:text-text-primary hover:bg-bg-hover transition-colors"
              aria-label={showFailedJobs ? 'Collapse failed jobs' : 'Expand failed jobs'}
            >
              {#if showFailedJobs}
                <ChevronUp class="w-4 h-4" />
              {:else}
                <ChevronDown class="w-4 h-4" />
              {/if}
            </button>
          </div>
          {#if showFailedJobs}
            <div class="grid gap-3">
              {#each filteredFailedJobs as job, i}
                <JobCard
                  {job}
                  onResume={resumeJob}
                  isResuming={resumingJobs.has(job.id)}
                  animationDelay={i * 50}
                />
              {/each}
            </div>
          {/if}
        </div>
      {/if}
    </div>
    {/if}
  {/if}
</div>
