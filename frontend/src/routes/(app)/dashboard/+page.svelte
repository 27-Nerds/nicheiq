<script lang="ts">
  import { page } from '$app/stores';
  import { onDestroy } from 'svelte';
  import { browser } from '$app/environment';
  import { SvelteMap, SvelteSet } from 'svelte/reactivity';
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
    RotateCw,
    ChevronDown,
    ChevronUp,
    Sparkles,
    X,
    AlertCircle,
    FolderOpen,
    ShieldCheck,
    RefreshCw,
    MoreVertical,
    Download
  } from 'lucide-svelte';
  import { showNewResearchModal } from '$lib/stores/newResearchModal';

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
  }

  const TOTAL_STAGES = 16; // Fallback - actual value comes from job.totalStages

  let { data } = $props();

  const session = $derived($page.data.session);
  const initialJobs = $derived(data.jobs as Job[]);

  // Track SSE connections and live job updates
  let eventSources = new SvelteMap<string, EventSource>();
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
        const es = eventSources.get(job.id);
        if (es) {
          es.close();
          eventSources.delete(job.id);
        }
      }
    } catch (err) {
      console.error('Cancel failed:', err);
    } finally {
      cancellingJobs.delete(job.id);
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

  // Translate raw API errors into user-friendly messages
  function getHumanReadableError(errorMessage: string | null): { summary: string; suggestion: string } {
    if (!errorMessage) {
      return { summary: 'Research failed', suggestion: 'Try again or contact support.' };
    }

    const error = errorMessage.toLowerCase();

    // === USER-ACTIONABLE ERRORS ===

    // Empty/invalid niche input
    if (error.includes('cannot be empty') || error.includes('niche description')) {
      return {
        summary: 'Invalid niche',
        suggestion: 'Please provide a more descriptive niche.'
      };
    }

    // No social content found (common for obscure niches)
    if (error.includes('no social content') || error.includes('no reddit') || error.includes('no twitter')) {
      return {
        summary: 'No discussions found',
        suggestion: 'Try a broader or more popular niche topic.'
      };
    }

    // Cancelled by user
    if (error.includes('cancelled') || error.includes('canceled')) {
      return {
        summary: 'Cancelled',
        suggestion: 'You cancelled this research.'
      };
    }

    // Insufficient credits (shouldn't happen but handle gracefully)
    if (error.includes('insufficient') && error.includes('credit')) {
      return {
        summary: 'Insufficient credits',
        suggestion: 'Purchase more credits to continue researching.'
      };
    }

    // Timeout errors
    if (error.includes('timeout') || error.includes('timed out')) {
      return {
        summary: 'Research took too long',
        suggestion: 'Try with a more specific niche.'
      };
    }

    // No results found (generic)
    if (error.includes('no results') || error.includes('not found') || error.includes('no data')) {
      return {
        summary: 'No data found for this niche',
        suggestion: 'Try a different or broader niche.'
      };
    }

    // === SYSTEM ERRORS (not user's fault) ===

    // Quality gate failures (internal threshold not met)
    if (error.includes('quality gate') || error.includes('confidence') || error.includes('threshold')) {
      return {
        summary: 'Quality check failed',
        suggestion: "The research didn't meet quality standards. Your credit was refunded."
      };
    }

    // Stage prerequisite errors (internal pipeline issue)
    if (error.includes('requires') && error.includes('stage')) {
      return {
        summary: 'Pipeline error',
        suggestion: 'An internal error occurred. Your credit was refunded.'
      };
    }

    // DataForSEO API errors
    if (error.includes('dataforseo')) {
      return {
        summary: 'SEO data unavailable',
        suggestion: 'External SEO service issue. Try again later.'
      };
    }

    // Rate limiting / quota errors
    if (error.includes('rate limit') || error.includes('quota') || error.includes('429')) {
      return {
        summary: 'Service temporarily busy',
        suggestion: 'Wait a few minutes and try again.'
      };
    }

    // API configuration errors (400 errors)
    if (error.includes('400') || error.includes('invalid_request') || error.includes('unsupported_parameter')) {
      return {
        summary: 'Configuration issue',
        suggestion: 'This is on our end. Your credit was refunded automatically.'
      };
    }

    // Authentication / API key errors
    if (error.includes('401') || error.includes('403') || error.includes('authentication') || error.includes('api key')) {
      return {
        summary: 'Service connection issue',
        suggestion: 'This is on our end. Try again later.'
      };
    }

    // Server errors
    if (error.includes('500') || error.includes('502') || error.includes('503') || error.includes('server')) {
      return {
        summary: 'Server error',
        suggestion: 'Our systems are having issues. Try again later.'
      };
    }

    // Default fallback
    return {
      summary: 'Research failed',
      suggestion: 'Try again or contact support if the issue persists.'
    };
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
              {@const isRunning = job.status.toUpperCase() === 'RUNNING'}
              {@const isPending = job.status.toUpperCase() === 'PENDING'}
              {@const isQueued = job.status.toUpperCase() === 'QUEUED'}
              {@const totalStages = job.totalStages || TOTAL_STAGES}

              {#if isRunning}
                <!-- RUNNING Card: Compact with inline progress -->
                <div
                  class="card hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200 border-l-2 border-l-warning animate-fade-slide-in"
                  style="animation-delay: {i * 50}ms"
                >
                  <!-- Header row -->
                  <div class="flex items-center justify-between gap-4 mb-3">
                    <div class="flex items-center gap-2.5 min-w-0">
                      <span class="w-2 h-2 rounded-full bg-warning animate-pulse shrink-0"></span>
                      <h3 class="text-base font-semibold text-text-primary truncate">
                        {formatNicheTitle(job.niche)}
                      </h3>
                    </div>
                    {#if job.startedAt}
                      <span class="text-xs font-medium text-warning shrink-0">
                        {formatElapsedTime(job.startedAt)}
                      </span>
                    {/if}
                  </div>

                  <!-- Progress row -->
                  <div class="flex items-center gap-3">
                    <div class="flex-1 h-1.5 bg-bg-surface rounded-full overflow-hidden">
                      <div class="h-full bg-warning rounded-full transition-all duration-300 animate-shimmer" style="width: {job.progressPercent}%"></div>
                    </div>
                    <span class="text-xs text-text-muted whitespace-nowrap">
                      {job.currentStageName || 'Starting'} ({job.stagesCompleted}/{totalStages})
                    </span>
                    <div class="flex items-center gap-1 shrink-0">
                      <button
                        onclick={() => cancelJob(job)}
                        disabled={cancellingJobs.has(job.id)}
                        class="p-1.5 rounded-md text-text-muted hover:text-error hover:bg-error/5 transition-colors"
                        title="Cancel"
                        aria-label="Cancel research"
                      >
                        {#if cancellingJobs.has(job.id)}
                          <Loader2 class="w-4 h-4 animate-spin" />
                        {:else}
                          <X class="w-4 h-4" />
                        {/if}
                      </button>
                      <a href="/jobs/{job.id}" class="btn-secondary text-sm py-1.5 px-3">
                        View <ArrowRight class="w-3.5 h-3.5" />
                      </a>
                    </div>
                  </div>
                </div>

              {:else}
                <!-- QUEUED/PENDING Card: Simplified single-row -->
                <div
                  class="card hover:shadow-md transition-all duration-200 border-l-2 border-l-secondary/60 bg-bg-surface/50 animate-fade-slide-in"
                  style="animation-delay: {i * 50}ms"
                >
                  <div class="flex items-center justify-between gap-4">
                    <div class="flex items-center gap-2.5 min-w-0">
                      <Clock class="w-4 h-4 text-secondary shrink-0" />
                      <h3 class="text-base font-medium text-text-secondary truncate">
                        {formatNicheTitle(job.niche)}
                      </h3>
                    </div>
                    <div class="flex items-center gap-3 shrink-0">
                      <span class="text-xs text-text-muted">
                        {#if job.queuePosition === 1}
                          Next up
                        {:else if job.queuePosition}
                          Position {job.queuePosition}
                        {:else}
                          Queued
                        {/if}
                      </span>
                      <button
                        onclick={() => cancelJob(job)}
                        disabled={cancellingJobs.has(job.id)}
                        class="text-xs px-2 py-0.5 rounded text-text-muted bg-bg-surface border border-border/50 hover:text-error hover:bg-error/10 hover:border-error/20 transition-colors"
                        aria-label="Cancel research"
                      >
                        {#if cancellingJobs.has(job.id)}
                          <Loader2 class="w-3 h-3 animate-spin inline" />
                        {:else}
                          Cancel
                        {/if}
                      </button>
                    </div>
                  </div>
                </div>
              {/if}
            {/each}
          </div>
        </div>
      {/if}

      <!-- Failed Jobs Section -->
      {#if filteredFailedJobs.length > 0}
        {#if filteredActiveJobs.length > 0}
          <div class="my-6">
            <div class="h-px bg-gradient-to-r from-transparent via-border-emphasis/50 to-transparent"></div>
          </div>
        {/if}
        <div class="space-y-4">
          <div class="flex items-center gap-3">
            <div class="w-1 h-6 rounded-full bg-error"></div>
            <h2 class="text-sm font-display font-semibold text-text-primary uppercase tracking-wide">
              Failed
            </h2>
            <span class="text-xs font-mono text-error bg-error/10 px-2 py-0.5 rounded-full">
              {filteredFailedJobs.length}
            </span>
          </div>
          <div class="grid gap-3">
            {#each filteredFailedJobs as job, i}
              {@const humanError = getHumanReadableError(job.errorMessage)}
              <div
                class="card hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200 border-l-2 border-l-error animate-fade-slide-in"
                style="animation-delay: {i * 50}ms"
              >
                <div class="flex flex-col sm:flex-row sm:items-start gap-4">
                  <div class="flex-1 min-w-0">
                    <!-- Title Row with dot indicator -->
                    <div class="flex items-center gap-2.5 mb-2">
                      <span class="w-2 h-2 rounded-full bg-error shrink-0"></span>
                      <h3 class="text-base font-semibold text-text-primary truncate">
                        {formatNicheTitle(job.niche)}
                      </h3>
                      <span class="text-xs text-text-muted ml-auto" title={formatDate(job.createdAt)}>
                        {formatRelativeDate(job.createdAt)}
                      </span>
                    </div>

                    <!-- User-Friendly Error Container -->
                    {#if job.errorMessage}
                      <div class="mt-3 p-3 rounded-lg bg-error/5 border border-error/10">
                        <div class="flex items-start gap-2">
                          <AlertCircle class="w-4 h-4 text-error shrink-0 mt-0.5" />
                          <div class="flex-1">
                            <p class="text-sm font-medium text-error">
                              {humanError.summary}
                            </p>
                            <p class="text-xs text-text-muted mt-0.5">
                              {humanError.suggestion}
                            </p>
                          </div>
                        </div>
                      </div>
                    {/if}

                    <!-- Credit Refund Indicator -->
                    {#if job.creditRefunded}
                      <div class="flex items-center gap-1.5 mt-2">
                        <CheckCircle class="w-3.5 h-3.5 text-success" />
                        <span class="text-xs text-success font-medium">Credit refunded</span>
                      </div>
                    {/if}
                  </div>

                  <!-- Action Buttons -->
                  <div class="flex items-center gap-2 shrink-0">
                    <button
                      onclick={() => resumeJob(job)}
                      disabled={resumingJobs.has(job.id)}
                      class="btn-primary flex items-center gap-2"
                      title="Resume from last checkpoint (no credit charge)"
                    >
                      <RotateCw class="w-4 h-4 {resumingJobs.has(job.id) ? 'animate-spin' : ''}" />
                      {resumingJobs.has(job.id) ? 'Resuming...' : 'Resume'}
                    </button>
                    <a href="/jobs/{job.id}" class="btn-secondary">
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
              <div
                class="card hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200 border-l-2 border-l-success animate-fade-slide-in"
                style="animation-delay: {i * 50}ms"
              >
                <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <!-- Left: Title + timestamp -->
                  <div class="min-w-0 flex-1">
                    <div class="flex items-center gap-2.5">
                      <span class="w-2 h-2 rounded-full bg-success shrink-0"></span>
                      <h3 class="text-base font-semibold text-text-primary truncate">
                        {formatNicheTitle(job.niche)}
                      </h3>
                    </div>
                    <p class="text-xs text-text-muted mt-1 ml-[18px]">
                      Completed {formatRelativeDate(job.completedAt || job.createdAt)}
                    </p>
                  </div>

                  <!-- Right: Actions -->
                  <div class="flex items-center gap-2 shrink-0">
                    <a href="/jobs/{job.id}/report" class="btn-primary text-sm py-2 px-4">
                      View Report
                    </a>
                    {#if job.hasLandingPage}
                      <a
                        href="/api/jobs/{job.id}/landingpage"
                        target="_blank"
                        rel="noopener noreferrer"
                        class="btn-secondary text-sm py-2 px-4"
                      >
                        Landing Page
                        <ExternalLink class="w-3.5 h-3.5" />
                      </a>
                    {/if}
                    <!-- Overflow menu for downloads -->
                    <div class="relative" data-menu-container>
                      <button
                        onclick={(e) => toggleMenu(job.id, e)}
                        class="p-2 rounded-md text-text-muted hover:text-text-primary hover:bg-bg-hover transition-colors"
                        aria-label="More options"
                      >
                        <MoreVertical class="w-4 h-4" />
                      </button>
                      {#if openMenuId === job.id}
                        <div class="absolute right-0 top-full mt-1 bg-bg-elevated border border-border rounded-lg shadow-lg py-1 min-w-[160px] z-10">
                          <a
                            href="/api/jobs/{job.id}/reportjson"
                            download
                            class="flex items-center gap-2 px-3 py-2 text-sm text-text-secondary hover:bg-bg-hover hover:text-text-primary transition-colors"
                          >
                            <Download class="w-4 h-4" /> Export JSON
                          </a>
                          {#if job.hasLandingPage}
                            <a
                              href="/api/jobs/{job.id}/landingpage?download=true"
                              download
                              class="flex items-center gap-2 px-3 py-2 text-sm text-text-secondary hover:bg-bg-hover hover:text-text-primary transition-colors"
                            >
                              <Download class="w-4 h-4" /> Export HTML
                            </a>
                          {/if}
                        </div>
                      {/if}
                    </div>
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
