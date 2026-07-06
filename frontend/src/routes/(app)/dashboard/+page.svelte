<script lang="ts">
  import { page } from "$app/state";
  import { onDestroy, untrack } from "svelte";
  import { beforeNavigate } from "$app/navigation";
  import { browser } from "$app/environment";
  import { SvelteMap, SvelteSet } from "svelte/reactivity";
  import {
    subscribeToProgress,
    isTerminalStatus,
    getReportSummary,
  } from "$lib/api";
  import { INITIAL_VISIBLE_COMPLETED } from "$lib/config/dashboard";
  import {
    Plus,
    XCircle,
    Search,
    ChevronDown,
    ChevronUp,
    X,
  } from "lucide-svelte";
  import JobCard from "$lib/components/ui/JobCard.svelte";
  import JobsListTable from "$lib/components/job/JobsListTable.svelte";
  import Button from "$lib/components/ui/Button.svelte";
  import SectionDivider from "$lib/components/catalog/seo/SectionDivider.svelte";
  import StatStrip, {
    type Stat,
  } from "$lib/components/catalog/seo/StatStrip.svelte";
  import type { Job, ReportSummary } from "$lib/types/job";

  let { data } = $props();

  const session = $derived(page.data.session);
  const initialJobs = $derived(data.jobs as Job[]);
  const creditBalance = $derived((page.data.creditBalance as number) ?? 0);
  const firstName = $derived(session?.user?.name?.split(" ")[0] ?? "there");
  const monthYear = $derived(
    new Date().toLocaleDateString("en-US", { month: "long", year: "numeric" }),
  );

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

  const heroStats = $derived<Stat[]>([
    { value: jobs.length, label: "Total Research" },
    { value: completedCount, label: "Completed", tone: "go" },
    { value: inProgressCount, label: "In Progress", tone: "amber" },
    {
      value: creditBalance,
      label: "Credits",
      tone: creditBalance === 0 ? "amber" : "info",
    },
  ]);

  // Group jobs by category for visual separation.
  // "In Progress" is sorted strictly newest-first (by createdAt desc) so a job you
  // just launched always appears at the top — independent of the status-priority
  // ordering used for the global list/stats above.
  const activeJobs = $derived(
    jobs
      .filter((j) => ACTIVE_STATUSES.includes(j.status.toUpperCase()))
      .sort(
        (a, b) =>
          new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
      ),
  );
  const completedJobs = $derived(
    jobs.filter((j) => j.status.toUpperCase() === "COMPLETED"),
  );
  const failedJobs = $derived(
    jobs.filter((j) => j.status.toUpperCase() === "FAILED"),
  );

  // Collapsible state for completed jobs (constant lives in $lib/config/dashboard
  // and is shared with the +page.server.ts loader)
  let showAllCompleted = $state(false);

  // Report summaries for completed jobs. Seeded from server loader (first 6).
  // Lazy-extended client-side on Show More + on SSE→COMPLETED transitions.
  // untrack() avoids the "captures only initial value of `data`" warning —
  // the $effect below keeps these in sync with later loader runs.
  let summaries = $state<Record<string, ReportSummary>>(
    untrack(
      () => ({ ...((data.summariesByJobId ?? {}) as Record<string, ReportSummary>) }),
    ),
  );

  // Sync local summaries when loader re-runs (e.g. after invalidateAll())
  $effect(() => {
    summaries = {
      ...((data.summariesByJobId ?? {}) as Record<string, ReportSummary>),
    };
  });


  async function fetchSummariesFor(jobIds: string[]) {
    const needed = jobIds.filter((id) => !summaries[id]);
    if (needed.length === 0) return;
    const results = await Promise.allSettled(
      needed.map((id) => getReportSummary(id)),
    );
    const next = { ...summaries };
    results.forEach((r, i) => {
      if (r.status === "fulfilled" && r.value) next[needed[i]] = r.value;
    });
    summaries = next;
  }

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

  // Section divider numbering: only numbers sections that actually render,
  // so the user never sees gaps like "02 · COMPLETED" with no 01 above it.
  const sectionNums = $derived.by(() => {
    const nums: Record<"active" | "completed" | "failed", number | null> = {
      active: null,
      completed: null,
      failed: null,
    };
    let n = 1;
    if (filteredActiveJobs.length > 0) nums.active = n++;
    if (filteredCompletedJobs.length > 0) nums.completed = n++;
    if (filteredFailedJobs.length > 0) nums.failed = n++;
    return nums;
  });

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

  // Connect SSE only for jobs that are actively processing.
  // AWAITING_SELECTION/REGENERATING don't need SSE on the dashboard — nothing changes
  // server-side until the user acts. This also avoids exhausting the browser's
  // HTTP/1.1 connection limit (6 per hostname) with idle SSE connections.
  const SSE_STATUSES = ['PENDING', 'QUEUED', 'RUNNING', 'RUNNING_PHASE2'];

  $effect.pre(() => {
    const activeJobsList = initialJobs.filter(
      (j) => SSE_STATUSES.includes(j.status),
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

              // Lazy-fetch report summary for a job that just transitioned to
              // COMPLETED mid-session so its Trifecta dials appear without a
              // page reload.
              if (
                data.status.toUpperCase() === "COMPLETED" &&
                !summaries[job.id]
              ) {
                getReportSummary(job.id)
                  .then((s) => {
                    if (s) summaries = { ...summaries, [job.id]: s };
                  })
                  .catch(() => {
                    // 404 / network — card just renders without dials
                  });
              }

              // Cleanup subscription if job no longer needs live updates
              if (isTerminalStatus(data.status) || !SSE_STATUSES.includes(data.status)) {
                sseUnsubscribers.get(job.id)?.();
                sseUnsubscribers.delete(job.id);
                if (isTerminalStatus(data.status)) {
                  setTimeout(() => jobUpdates.delete(job.id), 5000);
                }
              }
            },
            (err) => console.warn(`SSE error for job ${job.id}:`, err.message),
          );

          sseUnsubscribers.set(job.id, unsubscribe);
        }
      }

      // Cleanup subscriptions for jobs no longer needing SSE
      for (const [jobId] of sseUnsubscribers) {
        const job = initialJobs.find((j) => j.id === jobId);
        if (!job || !SSE_STATUSES.includes(job.status)) {
          sseUnsubscribers.get(jobId)?.();
          sseUnsubscribers.delete(jobId);
        }
      }
    });
  });

  // Close SSE connections BEFORE navigation starts — frees HTTP/1.1 connection slots
  // so the next page's __data.json fetch isn't blocked by open EventSource connections.
  beforeNavigate(() => {
    sseUnsubscribers.forEach((unsubscribe) => unsubscribe());
    sseUnsubscribers.clear();
  });

  // Cleanup on destroy (fallback for non-navigation teardown)
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

<!-- Keyboard shortcut for search ("/" focus, Escape clears) -->
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
    if (e.key === "Escape" && document.activeElement === searchInput) {
      searchInput?.blur();
      searchQuery = "";
    }
  }}
/>

<div class="max-w-5xl mx-auto">
  <!-- Editorial hero (mono dateline kicker + display H1) -->
  <header class="dash-hero">
    <p class="dash-kicker">
      <span class="k-accent">YOUR RESEARCH</span>
      <span class="k-dot">·</span>
      <span>{monthYear}</span>
    </p>
    <h1 class="dash-h1">Welcome back, {firstName}</h1>
    <p class="dash-lede">Manage your market research reports</p>
  </header>

  <!-- Pro tip banner (show when no active jobs and has completed jobs, unless dismissed) -->
  {#if jobs.length > 0 && inProgressCount === 0 && completedCount > 0 && !tipDismissed}
    <div
      class="mb-6 px-4 py-3 rounded-lg border border-border bg-bg-elevated animate-fade-slide-in"
    >
      <div class="flex items-center justify-between gap-3">
        <p class="text-sm text-text-secondary">
          <span class="font-medium text-text-primary"
            >Ready for more insights?</span
          >
          {" "}Start another research to explore new market opportunities.
        </p>
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
  <div class="mb-8">
    <StatStrip stats={heroStats} emphasis />
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
          NicheIQ analyzes Reddit and Hacker News discussions, identifies pain
          points, and generates a comprehensive market research report — first
          ideas in ~15 minutes.
        </p>
        <Button href="/new" icon={Plus} label="Start Your First Research" class="btn-primary inline-flex text-base px-6 py-3" />
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
            <SectionDivider
              num={sectionNums.active}
              label="In Progress"
              metaText="{filteredActiveJobs.length} active"
            />
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
          <div class="space-y-4">
            <SectionDivider
              num={sectionNums.completed}
              label="Completed"
              metaText="{filteredCompletedJobs.length} reports"
            />
            <JobsListTable jobs={filteredVisibleCompleted} {summaries} />

            <!-- Show more/less button -->
            {#if filteredCompletedJobs.length > INITIAL_VISIBLE_COMPLETED}
              <button
                onclick={() => {
                  const wasCollapsed = !showAllCompleted;
                  showAllCompleted = !showAllCompleted;
                  if (wasCollapsed) {
                    // Fetch summaries for the just-revealed completed jobs,
                    // honoring the active search filter so we don't fetch
                    // cards that aren't even rendered.
                    const newlyRevealedIds = filteredCompletedJobs
                      .slice(INITIAL_VISIBLE_COMPLETED)
                      .map((j) => j.id);
                    void fetchSummariesFor(newlyRevealedIds);
                  }
                }}
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
          <div class="space-y-4">
            <SectionDivider num={sectionNums.failed} label="Failed">
              {#snippet right()}
                <span
                  class="text-[11px] font-mono text-text-muted tabular-nums"
                >
                  {filteredFailedJobs.length} failed
                </span>
                <button
                  onclick={() => (showFailedJobs = !showFailedJobs)}
                  class="p-1.5 rounded-md text-text-muted hover:text-text-primary hover:bg-bg-hover transition-colors"
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
              {/snippet}
            </SectionDivider>
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

<style>
  /* Editorial hero — mono dateline kicker + display H1, mirrors CatalogIndexHero. */
  .dash-hero {
    padding: 40px 0 28px;
    margin-bottom: 28px;
    border-bottom: 1px solid var(--color-border);
  }
  .dash-kicker {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    font-family: var(--font-mono);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    margin: 0 0 14px;
  }
  .dash-kicker .k-accent {
    color: var(--color-accent);
  }
  .dash-kicker .k-dot {
    opacity: 0.5;
  }
  .dash-h1 {
    font-family: var(--font-display);
    font-size: clamp(1.75rem, 4vw, 2.25rem);
    font-weight: 600;
    letter-spacing: -0.025em;
    line-height: 1.1;
    color: var(--color-text-primary);
    margin: 0;
  }
  .dash-lede {
    font-size: 15px;
    line-height: 1.6;
    color: var(--color-text-secondary);
    margin: 12px 0 0;
    max-width: 620px;
  }
</style>
