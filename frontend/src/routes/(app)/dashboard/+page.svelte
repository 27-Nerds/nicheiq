<script lang="ts">
  import { page } from "$app/stores";
  import { onDestroy, untrack } from "svelte";
  import { browser } from "$app/environment";
  import { SvelteMap, SvelteSet } from "svelte/reactivity";
  import { subscribeToProgress, isTerminalStatus } from "$lib/api";
  import {
    Plus,
    XCircle,
    Search,
    ChevronDown,
    ChevronUp,
    Telescope,
    X,
    Library,
    Trophy,
    FlaskConical,
  } from "lucide-svelte";
  import { showNewResearchModal } from "$lib/stores/newResearchModal";
  import JobCard from "$lib/components/ui/JobCard.svelte";
  import CategoryBar from "$lib/components/ui/CategoryBar.svelte";
  import StatCard from "$lib/components/ui/StatCard.svelte";
  import Button from "$lib/components/ui/Button.svelte";
  import type { Job } from "$lib/types/job";

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
      .map((job) => jobUpdates.get(job.id) || job)
      .sort((a, b) => {
        // Priority: Awaiting Selection > Running > Pending/Queued > Failed > Completed
        const statusPriority: Record<string, number> = {
          AWAITING_SELECTION: -1,
          RUNNING: 0,
          RUNNING_PHASE2: 0,
          REGENERATING: 0,
          PENDING: 1,
          QUEUED: 1,
          FAILED: 2,
          COMPLETED: 3,
        };
        const priorityA = statusPriority[a.status.toUpperCase()] ?? 4;
        const priorityB = statusPriority[b.status.toUpperCase()] ?? 4;

        if (priorityA !== priorityB) return priorityA - priorityB;

        // Within same priority, sort by date (newest first)
        return (
          new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
        );
      }),
  );

  // Stats counts
  const completedCount = $derived(
    jobs.filter((j) => j.status.toUpperCase() === "COMPLETED").length,
  );
  const ACTIVE_STATUSES = [
    "RUNNING",
    "PENDING",
    "QUEUED",
    "AWAITING_SELECTION",
    "REGENERATING",
    "RUNNING_PHASE2",
  ];

  const inProgressCount = $derived(
    jobs.filter((j) => ACTIVE_STATUSES.includes(j.status.toUpperCase())).length,
  );
  const failedCount = $derived(
    jobs.filter((j) => j.status.toUpperCase() === "FAILED").length,
  );

  // Group jobs by category for visual separation
  const activeJobs = $derived(
    jobs.filter((j) => ACTIVE_STATUSES.includes(j.status.toUpperCase())),
  );
  const completedJobs = $derived(
    jobs.filter((j) => j.status.toUpperCase() === "COMPLETED"),
  );
  const failedJobs = $derived(
    jobs.filter((j) => j.status.toUpperCase() === "FAILED"),
  );

  // Collapsible state for completed jobs
  const INITIAL_VISIBLE_COMPLETED = 6;
  let showAllCompleted = $state(false);

  // Collapsible state for failed jobs
  let showFailedJobs = $state(true);
  const visibleCompletedJobs = $derived(
    showAllCompleted
      ? completedJobs
      : completedJobs.slice(0, INITIAL_VISIBLE_COMPLETED),
  );
  const hasMoreCompleted = $derived(
    completedJobs.length > INITIAL_VISIBLE_COMPLETED,
  );

  // Search/filter state
  let searchQuery = $state("");
  const filteredActiveJobs = $derived(
    searchQuery.trim()
      ? activeJobs.filter((j) =>
          j.niche.toLowerCase().includes(searchQuery.toLowerCase()),
        )
      : activeJobs,
  );
  const filteredFailedJobs = $derived(
    searchQuery.trim()
      ? failedJobs.filter((j) =>
          j.niche.toLowerCase().includes(searchQuery.toLowerCase()),
        )
      : failedJobs,
  );
  const filteredCompletedJobs = $derived(
    searchQuery.trim()
      ? completedJobs.filter((j) =>
          j.niche.toLowerCase().includes(searchQuery.toLowerCase()),
        )
      : completedJobs,
  );
  const filteredVisibleCompleted = $derived(
    showAllCompleted
      ? filteredCompletedJobs
      : filteredCompletedJobs.slice(0, INITIAL_VISIBLE_COMPLETED),
  );
  const hasFilteredResults = $derived(
    filteredActiveJobs.length > 0 ||
      filteredFailedJobs.length > 0 ||
      filteredCompletedJobs.length > 0,
  );

  // Dismissable tip banner
  const TIP_DISMISSED_KEY = "nicheiq_tip_dismissed";
  let tipDismissed = $state(
    browser ? localStorage.getItem(TIP_DISMISSED_KEY) === "true" : false,
  );

  function dismissTip() {
    tipDismissed = true;
    if (browser) {
      localStorage.setItem(TIP_DISMISSED_KEY, "true");
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
    filteredActiveJobs.length +
      filteredFailedJobs.length +
      filteredCompletedJobs.length,
  );

  // Get effective job data (live update or initial)
  function getJobData(jobId: string): Job | undefined {
    return jobUpdates.get(jobId) || initialJobs.find((j) => j.id === jobId);
  }

  // Connect SSE for active jobs (including queued to catch status changes)
  // Use $effect.pre with untrack() to prevent reactive tracking of map mutations
  $effect.pre(() => {
    // Only track initialJobs for dependencies
    const activeJobsList = initialJobs.filter(
      (j) => !isTerminalStatus(j.status),
    );

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
            (err) => console.warn(`SSE error for job ${job.id}:`, err.message),
          );

          sseUnsubscribers.set(job.id, unsubscribe);
        }
      }

      // Cleanup subscriptions for jobs no longer active
      // Use initialJobs.find() instead of getJobData() to avoid reading jobUpdates
      for (const [jobId] of sseUnsubscribers) {
        const job = initialJobs.find((j) => j.id === jobId);
        if (!job || isTerminalStatus(job.status)) {
          sseUnsubscribers.get(jobId)?.();
          sseUnsubscribers.delete(jobId);
        }
      }
    });
  });

  // Cleanup on destroy
  onDestroy(() => {
    sseUnsubscribers.forEach((unsubscribe) => unsubscribe());
    sseUnsubscribers.clear();
  });

  // Resume a failed job from checkpoint (no credit charge)
  let resumingJobs = new SvelteSet<string>();

  async function resumeJob(job: Job) {
    if (resumingJobs.has(job.id)) return;

    resumingJobs.add(job.id);
    try {
      const res = await fetch(`/api/jobs/${job.id}/resume`, {
        method: "POST",
      });

      if (res.ok) {
        // Redirect to job page to see progress
        window.location.href = `/jobs/${job.id}`;
      } else {
        const data = await res.json();
        console.error("Resume failed:", data.error || "Unknown error");
      }
    } catch (err) {
      console.error("Resume failed:", err);
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
        method: "POST",
      });

      if (res.ok) {
        // Update local state to reflect cancellation
        jobUpdates.set(job.id, {
          ...job,
          status: "CANCELLED",
          errorMessage: "Cancelled by user",
        });

        // Close SSE connection for this job
        const unsubscribe = sseUnsubscribers.get(job.id);
        if (unsubscribe) {
          unsubscribe();
          sseUnsubscribers.delete(job.id);
        }
      }
    } catch (err) {
      console.error("Cancel failed:", err);
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
    if (
      e.key === "/" &&
      document.activeElement?.tagName !== "INPUT" &&
      document.activeElement?.tagName !== "TEXTAREA"
    ) {
      e.preventDefault();
      searchInput?.focus();
    }
    if (e.key === "Escape") {
      if (openMenuId) {
        closeMenu();
      } else if (document.activeElement === searchInput) {
        searchInput?.blur();
        searchQuery = "";
      }
    }
  }}
  onclick={(e) => {
    // Close overflow menu when clicking outside
    if (openMenuId) {
      const target = e.target as HTMLElement;
      if (!target.closest("[data-menu-container]")) {
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
            Welcome back{session?.user?.name ? `, ${session.user.name}` : ""}
          </h1>
          {#if inProgressCount > 0}
            <span
              class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-warning/10 text-warning border border-warning/20 animate-pulse"
            >
              <span class="w-1.5 h-1.5 rounded-full bg-warning"></span>
              {inProgressCount} active
            </span>
          {/if}
        </div>
        <p class="text-text-muted">Manage your market research reports</p>
      </div>
      {#if jobs.length > 0 && inProgressCount === 0}
        <Button onclick={() => ($showNewResearchModal = true)} icon={Plus} label="New Research" class="btn-primary hidden sm:inline-flex" />
      {/if}
    </div>
  </div>

  <!-- Pro tip banner (show when no active jobs and has completed jobs, unless dismissed) -->
  {#if jobs.length > 0 && inProgressCount === 0 && completedCount > 0 && !tipDismissed}
    <div
      class="mb-6 p-4 rounded-lg bg-accent/5 border border-accent/10 animate-fade-slide-in"
    >
      <div class="flex items-center justify-between gap-3">
        <div class="flex items-center gap-3">
          <div class="p-2 rounded-lg bg-accent/10">
            <Telescope class="w-4 h-4 text-accent" />
          </div>
          <p class="text-sm text-text-secondary">
            <span class="font-medium text-text-primary"
              >Ready for more insights?</span
            >
            {" "}Start another research to explore new market opportunities.
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
    <StatCard icon={Library} value={jobs.length} label="Total Research" color="accent" />
    <StatCard icon={Trophy} value={completedCount} label="Completed" color="success" />
    <StatCard icon={FlaskConical} value={inProgressCount} label="In Progress" color="warning" />
  </div>

  <!-- Search bar (only show when there are jobs) -->
  {#if jobs.length > 0}
    <div class="mb-6 flex flex-col sm:flex-row sm:items-center gap-3">
      <div class="relative">
        <Search
          class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted"
        />
        <input
          type="text"
          bind:this={searchInput}
          bind:value={searchQuery}
          placeholder="Search research..."
          class="input input-with-icon w-full sm:w-72"
        />
        <div
          class="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-2"
        >
          {#if searchQuery}
            <button
              onclick={() => (searchQuery = "")}
              aria-label="Clear search"
              class="text-text-muted hover:text-text-primary transition-colors"
            >
              <XCircle class="w-4 h-4" />
            </button>
          {:else}
            <kbd
              class="hidden sm:inline-flex items-center justify-center w-5 h-5 text-[10px] font-mono text-text-muted bg-bg-elevated border border-border rounded shadow-sm"
              >/</kbd
            >
          {/if}
        </div>
      </div>
      {#if searchQuery}
        <p class="text-sm text-text-muted">
          {totalFilteredCount}
          {totalFilteredCount === 1 ? "result" : "results"}
        </p>
      {/if}
    </div>
  {/if}

  <!-- Job List -->
  {#if jobs.length === 0}
    <div
      class="rounded-xl border border-border bg-bg-elevated text-center py-16 px-6"
    >
        <div
          class="w-20 h-20 mx-auto mb-6 rounded-2xl bg-accent/10 border border-accent/20 flex items-center justify-center"
        >
          <Search class="w-10 h-10 text-accent" />
        </div>
        <h2 class="text-2xl font-bold text-text-primary mb-3">
          No research yet
        </h2>
        <p class="text-text-secondary mb-8 max-w-lg mx-auto leading-relaxed">
          NicheIQ analyzes Reddit discussions, identifies pain points, and
          generates a comprehensive market research report in minutes.
        </p>
        <Button onclick={() => ($showNewResearchModal = true)} icon={Plus} label="Start Your First Research" class="btn-primary inline-flex text-base px-6 py-3" />
        <p class="text-xs text-text-muted mt-4">
          Two-phase AI research with your input at the gate. ~35 minutes total.
        </p>
    </div>
  {:else}
    <!-- No search results -->
    {#if searchQuery && !hasFilteredResults}
      <div class="card text-center py-12">
        <Search class="w-12 h-12 mx-auto mb-4 text-text-muted" />
        <h3 class="text-lg font-semibold text-text-primary mb-2">
          No results found
        </h3>
        <p class="text-text-muted mb-4">No research matches "{searchQuery}"</p>
        <Button onclick={() => (searchQuery = "")} label="Clear search" class="btn-secondary inline-flex" />
      </div>
    {:else}
      <div class="space-y-6">
        <!-- Active Jobs Section -->
        {#if filteredActiveJobs.length > 0}
          <div class="space-y-4">
            <CategoryBar title="In Progress" color="warning" count={filteredActiveJobs.length} margin="mb-0" />
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
            <div class="my-6 h-px bg-border"></div>
          {/if}
          <div class="space-y-4">
            <CategoryBar title="Completed" color="success" count={filteredCompletedJobs.length} margin="mb-0" />
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
                onclick={() => (showAllCompleted = !showAllCompleted)}
                class="w-full py-3 px-4 rounded-lg border border-border bg-bg-surface hover:bg-bg-hover text-text-secondary hover:text-text-primary transition-colors flex items-center justify-center gap-2 text-sm font-medium"
              >
                {#if showAllCompleted}
                  <ChevronUp class="w-4 h-4" />
                  Show less
                {:else}
                  <ChevronDown class="w-4 h-4" />
                  Show {filteredCompletedJobs.length -
                    INITIAL_VISIBLE_COMPLETED} more completed
                {/if}
              </button>
            {/if}
          </div>
        {/if}

        <!-- Failed Jobs Section -->
        {#if filteredFailedJobs.length > 0}
          {#if filteredActiveJobs.length > 0 || filteredCompletedJobs.length > 0}
            <div class="my-6 h-px bg-border"></div>
          {/if}
          <div class="space-y-4">
            <CategoryBar title="Failed" color="error" count={filteredFailedJobs.length} margin="mb-0">
              <button
                onclick={() => (showFailedJobs = !showFailedJobs)}
                class="ml-auto p-1.5 rounded-md text-text-muted hover:text-text-primary hover:bg-bg-hover transition-colors"
                aria-label={showFailedJobs
                  ? "Collapse failed jobs"
                  : "Expand failed jobs"}
              >
                {#if showFailedJobs}
                  <ChevronUp class="w-4 h-4" />
                {:else}
                  <ChevronDown class="w-4 h-4" />
                {/if}
              </button>
            </CategoryBar>
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
