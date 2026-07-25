<script lang="ts">
  import { page } from "$app/state";
  import { onDestroy, untrack } from "svelte";
  import { beforeNavigate } from "$app/navigation";
  import { browser } from "$app/environment";
  import { invalidateAll } from "$app/navigation";
  import { SvelteMap, SvelteSet } from "svelte/reactivity";
  import {
    subscribeToProgress,
    isTerminalStatus,
    getReportSummary,
  } from "$lib/api";
  import { INITIAL_VISIBLE_COMPLETED } from "$lib/config/dashboard";
  import {
    statusMeta,
    bucketOf,
    isLive,
    verdictColor,
    scoreColor,
    toScore100,
    type LifecycleBucket,
  } from "$lib/config/jobStatus";
  import { getAdjustedStageCounts } from "$lib/utils/stages";
  import {
    Plus,
    Search,
    XCircle,
    X,
    AlertTriangle,
    RotateCw,
    RotateCcw,
    ArrowRight,
    ChevronDown,
    Loader2,
    Compass,
    Bookmark,
  } from "lucide-svelte";
  import type { Job, ReportSummary } from "$lib/types/job";
  import type { SavedIdeaItem, SavedPainPointItem } from "$lib/types/saved";
  import SavedIdeaCard from "../ideas/saved/SavedIdeaCard.svelte";
  import LockedSavedCard from "../ideas/saved/LockedSavedCard.svelte";
  import SavedPainTable from "../ideas/saved/SavedPainTable.svelte";
  import UndoToast from "../ideas/saved/UndoToast.svelte";
  import { formatDistanceToNow } from "../ideas/saved/formatRelative";
  import SidebarNav from "$lib/components/nav/SidebarNav.svelte";
  import SidebarGroup from "$lib/components/nav/SidebarGroup.svelte";
  import SidebarDivider from "$lib/components/nav/SidebarDivider.svelte";
  import SidebarNavItem from "$lib/components/nav/SidebarNavItem.svelte";

  // Relative "…ago" for a job's creation time. Entry-mode ("idea"/"discovery")
  // is internal jargon and intentionally NOT surfaced on the dashboard.
  const ago = (iso: string) => `${formatDistanceToNow(iso)} ago`;

  let { data } = $props();

  const session = $derived(page.data.session);
  const initialJobs = $derived(data.jobs as Job[]);
  const firstName = $derived(session?.user?.name?.split(" ")[0] ?? "there");

  // ── Live job updates (SSE) merged over the server snapshot ──
  const sseUnsubscribers = new Map<string, () => void>();
  let jobUpdates = new SvelteMap<string, Job>();

  const jobs = $derived(
    initialJobs
      .map((job) => jobUpdates.get(job.id) || job)
      .sort(
        (a, b) =>
          new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
      ),
  );

  // ── Lifecycle buckets (global — drives the summary line + SSE) ──
  const reviewJobs = $derived(jobs.filter((j) => bucketOf(j) === "review"));
  const progressJobs = $derived(jobs.filter((j) => bucketOf(j) === "progress"));
  const doneJobs = $derived(jobs.filter((j) => bucketOf(j) === "done"));
  const failedJobs = $derived(jobs.filter((j) => bucketOf(j) === "failed"));
  const archivedJobs = $derived(jobs.filter((j) => bucketOf(j) === "archived"));

  // ── Tabs + filter rail ──
  let tab = $state<"research" | "saved">("research");
  let filter = $state<"all" | LifecycleBucket>("all");
  let archivedOpen = $state(false);

  // ── Search ──
  let searchQuery = $state("");
  let searchInput = $state<HTMLInputElement | null>(null);
  const q = $derived(searchQuery.trim().toLowerCase());
  const matches = (j: Job) => !q || j.niche.toLowerCase().includes(q);

  const fReview = $derived(reviewJobs.filter(matches));
  const fProgress = $derived(progressJobs.filter(matches));
  const fDone = $derived(doneJobs.filter(matches));
  const fFailed = $derived(failedJobs.filter(matches));
  const fArchived = $derived(archivedJobs.filter(matches));

  const buckets = $derived([
    { key: "all", label: "All research", count: fReview.length + fProgress.length + fDone.length + fFailed.length + fArchived.length, color: "var(--color-text-muted)" },
    { key: "review", label: "Ready to review", count: fReview.length, color: "var(--color-accent)" },
    { key: "progress", label: "In progress", count: fProgress.length, color: "var(--color-info-dark)" },
    { key: "done", label: "Completed", count: fDone.length, color: "var(--color-success-text)" },
    { key: "failed", label: "Failed", count: fFailed.length, color: "var(--color-error-text)" },
    { key: "archived", label: "Archived", count: fArchived.length, color: "var(--color-text-muted)" },
  ] as const);
  const show = (b: string) => filter === "all" || filter === b;
  const archivedShown = $derived(archivedOpen || filter === "archived");
  const hasAnyVisible = $derived(
    fReview.length + fProgress.length + fDone.length + fFailed.length + fArchived.length > 0,
  );

  // ── Completed: cap initial render, lazy-fetch summaries on expand ──
  let showAllCompleted = $state(false);
  const visibleDone = $derived(
    showAllCompleted ? fDone : fDone.slice(0, INITIAL_VISIBLE_COMPLETED),
  );
  const hasMoreDone = $derived(fDone.length > INITIAL_VISIBLE_COMPLETED);

  let summaries = $state<Record<string, ReportSummary>>(
    untrack(() => ({ ...((data.summariesByJobId ?? {}) as Record<string, ReportSummary>) })),
  );
  $effect(() => {
    summaries = { ...((data.summariesByJobId ?? {}) as Record<string, ReportSummary>) };
  });

  async function fetchSummariesFor(jobIds: string[]) {
    const needed = jobIds.filter((id) => !summaries[id]);
    if (needed.length === 0) return;
    const results = await Promise.allSettled(needed.map((id) => getReportSummary(id)));
    const next = { ...summaries };
    results.forEach((r, i) => {
      if (r.status === "fulfilled" && r.value) next[needed[i]] = r.value;
    });
    summaries = next;
  }

  function toggleAllCompleted() {
    const wasCollapsed = !showAllCompleted;
    showAllCompleted = !showAllCompleted;
    if (wasCollapsed) {
      void fetchSummariesFor(fDone.slice(INITIAL_VISIBLE_COMPLETED).map((j) => j.id));
    }
  }

  // ── Completed-card helpers ──
  function reportHref(job: Job): string {
    return job.hasReport ? `/jobs/${job.id}/report` : `/jobs/${job.id}`;
  }
  // prefill /new with the niche so a re-run starts pre-loaded
  const rerunHref = (niche: string) => `/new?niche=${encodeURIComponent(niche)}`;

  // ══════════════════════════════════════════════════════════════
  // SSE — connect only for jobs actively processing server-side.
  // ══════════════════════════════════════════════════════════════
  const SSE_STATUSES = ["PENDING", "QUEUED", "RUNNING", "RUNNING_PHASE2"];

  $effect.pre(() => {
    const activeJobsList = initialJobs.filter((j) => SSE_STATUSES.includes(j.status));
    untrack(() => {
      for (const job of activeJobsList) {
        if (!sseUnsubscribers.has(job.id)) {
          const unsubscribe = subscribeToProgress(
            job.id,
            (d) => {
              jobUpdates.set(job.id, d as Job);
              if (d.status.toUpperCase() === "COMPLETED" && !summaries[job.id]) {
                getReportSummary(job.id)
                  .then((s) => {
                    if (s) summaries = { ...summaries, [job.id]: s };
                  })
                  .catch(() => {});
              }
              if (isTerminalStatus(d.status) || !SSE_STATUSES.includes(d.status)) {
                sseUnsubscribers.get(job.id)?.();
                sseUnsubscribers.delete(job.id);
                if (isTerminalStatus(d.status)) {
                  setTimeout(() => jobUpdates.delete(job.id), 5000);
                }
              }
            },
            (err) => console.warn(`SSE error for job ${job.id}:`, err.message),
          );
          sseUnsubscribers.set(job.id, unsubscribe);
        }
      }
      for (const [jobId] of sseUnsubscribers) {
        const job = initialJobs.find((j) => j.id === jobId);
        if (!job || !SSE_STATUSES.includes(job.status)) {
          sseUnsubscribers.get(jobId)?.();
          sseUnsubscribers.delete(jobId);
        }
      }
    });
  });

  beforeNavigate(() => {
    sseUnsubscribers.forEach((u) => u());
    sseUnsubscribers.clear();
  });
  onDestroy(() => {
    sseUnsubscribers.forEach((u) => u());
    sseUnsubscribers.clear();
  });

  // ── Resume a hard-failed job from checkpoint ──
  let resumingJobs = new SvelteSet<string>();
  async function resumeJob(job: Job) {
    if (resumingJobs.has(job.id)) return;
    resumingJobs.add(job.id);
    try {
      const res = await fetch(`/api/jobs/${job.id}/resume`, { method: "POST" });
      if (res.ok) {
        window.location.href = `/jobs/${job.id}`;
      } else {
        const d = await res.json();
        console.error("Resume failed:", d.error || "Unknown error");
      }
    } catch (err) {
      console.error("Resume failed:", err);
    } finally {
      resumingJobs.delete(job.id);
    }
  }

  // ── Cancel an active job ──
  let cancellingJobs = new SvelteSet<string>();
  async function cancelJob(job: Job) {
    if (cancellingJobs.has(job.id)) return;
    cancellingJobs.add(job.id);
    try {
      const res = await fetch(`/api/jobs/${job.id}/cancel`, { method: "POST" });
      if (res.ok) {
        jobUpdates.set(job.id, {
          ...job,
          status: "CANCELLED",
          errorMessage: "Cancelled by user",
        });
        sseUnsubscribers.get(job.id)?.();
        sseUnsubscribers.delete(job.id);
      }
    } catch (err) {
      console.error("Cancel failed:", err);
    } finally {
      cancellingJobs.delete(job.id);
    }
  }

  // ══════════════════════════════════════════════════════════════
  // SAVED TAB — reuse the docket components with optimistic mutations.
  // Remix + note-filter live on the full /ideas/saved docket (linked).
  // ══════════════════════════════════════════════════════════════
  let savedIdeas = $state<SavedIdeaItem[]>(untrack(() => (data.savedIdeas ?? []) as SavedIdeaItem[]));
  let savedPains = $state<SavedPainPointItem[]>(untrack(() => (data.savedPainPoints ?? []) as SavedPainPointItem[]));
  let savedCounts = $state(untrack(() => data.savedCounts ?? { ideas: 0, painPoints: 0 }));
  $effect(() => {
    savedIdeas = (data.savedIdeas ?? []) as SavedIdeaItem[];
    savedPains = (data.savedPainPoints ?? []) as SavedPainPointItem[];
    savedCounts = data.savedCounts ?? { ideas: 0, painPoints: 0 };
  });
  const savedTotal = $derived(savedCounts.ideas + savedCounts.painPoints);

  // Summary tail — only the non-zero lifecycle segments, so an all-awaiting
  // account doesn't read "· 0 in progress · 0 completed".
  const summaryTail = $derived(
    [
      progressJobs.length ? `${progressJobs.length} in progress` : null,
      doneJobs.length ? `${doneJobs.length} completed` : null,
    ]
      .filter(Boolean)
      .join(" · "),
  );

  type PendingUndo =
    | { kind: "idea"; item: SavedIdeaItem; index: number }
    | { kind: "painPoint"; item: SavedPainPointItem; index: number };
  let pendingUndo = $state<PendingUndo | null>(null);

  function unsaveIdea(item: SavedIdeaItem) {
    const idx = savedIdeas.findIndex((i) => i.id === item.id);
    if (idx === -1) return;
    savedIdeas = savedIdeas.filter((i) => i.id !== item.id);
    savedCounts = { ...savedCounts, ideas: savedCounts.ideas - 1 };
    pendingUndo = { kind: "idea", item, index: idx };
  }
  function unsavePain(item: SavedPainPointItem) {
    const idx = savedPains.findIndex((p) => p.id === item.id);
    if (idx === -1) return;
    savedPains = savedPains.filter((p) => p.id !== item.id);
    savedCounts = { ...savedCounts, painPoints: savedCounts.painPoints - 1 };
    pendingUndo = { kind: "painPoint", item, index: idx };
  }
  function undoLast() {
    if (!pendingUndo) return;
    if (pendingUndo.kind === "idea") {
      const restored = [...savedIdeas];
      restored.splice(pendingUndo.index, 0, pendingUndo.item);
      savedIdeas = restored;
      savedCounts = { ...savedCounts, ideas: savedCounts.ideas + 1 };
    } else {
      const restored = [...savedPains];
      restored.splice(pendingUndo.index, 0, pendingUndo.item);
      savedPains = restored;
      savedCounts = { ...savedCounts, painPoints: savedCounts.painPoints + 1 };
    }
    pendingUndo = null;
  }
  async function commitUnsave() {
    if (!pendingUndo) return;
    const u = pendingUndo;
    pendingUndo = null;
    try {
      const path =
        u.kind === "idea"
          ? `/api/saves/ideas/${u.item.ideaId}`
          : `/api/saves/pain-points/${u.item.painPointId}`;
      const res = await fetch(path, { method: "DELETE", credentials: "same-origin" });
      if (!res.ok && res.status !== 404) throw new Error(`Delete failed: ${res.status}`);
    } catch (err) {
      console.error("Unsave commit failed:", err);
      await invalidateAll();
    }
  }
  async function patchIdeaNotes(item: SavedIdeaItem, notes: string | null) {
    savedIdeas = savedIdeas.map((i) => (i.id === item.id && !i.locked ? { ...i, notes } : i));
    try {
      const res = await fetch(`/api/saves/ideas/${item.ideaId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ notes }),
      });
      if (!res.ok) throw new Error(`PATCH failed: ${res.status}`);
    } catch (err) {
      console.error("Note save failed:", err);
      await invalidateAll();
    }
  }
  async function patchPainNotes(item: SavedPainPointItem, notes: string | null) {
    savedPains = savedPains.map((p) => (p.id === item.id && !p.locked ? { ...p, notes } : p));
    try {
      const res = await fetch(`/api/saves/pain-points/${item.painPointId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ notes }),
      });
      if (!res.ok) throw new Error(`PATCH failed: ${res.status}`);
    } catch (err) {
      console.error("Note save failed:", err);
      await invalidateAll();
    }
  }
</script>

<svelte:head>
  <title>Dashboard - NicheIQ</title>
</svelte:head>

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

<div class="dash">
  <!-- ── LEFT SIDEBAR (shared sidebar primitives) ── -->
  <SidebarNav class="dash-side" label="Dashboard views">
    <SidebarGroup label="Your research">
      <SidebarNavItem
        active={tab === "research"}
        onclick={() => (tab = "research")}
        aria-current={tab === "research" ? "true" : undefined}
      >
        {#snippet leading()}<Compass class="sidebar-nav-ic" aria-hidden="true" />{/snippet}
        Research
        {#snippet trailing()}<span class="nav-count">{jobs.length}</span>{/snippet}
      </SidebarNavItem>
      <SidebarNavItem
        active={tab === "saved"}
        onclick={() => (tab = "saved")}
        aria-current={tab === "saved" ? "true" : undefined}
      >
        {#snippet leading()}<Bookmark class="sidebar-nav-ic" aria-hidden="true" />{/snippet}
        Saved ideas
        {#snippet trailing()}<span class="nav-count">{savedTotal}</span>{/snippet}
      </SidebarNavItem>
    </SidebarGroup>

    {#if tab === "research" && jobs.length > 0}
      <SidebarDivider />
      <SidebarGroup label="Filter">
        {#each buckets as b (b.key)}
          <SidebarNavItem
            active={filter === b.key}
            onclick={() => (filter = b.key)}
            aria-current={filter === b.key ? "true" : undefined}
          >
            {#snippet leading()}<span class="nav-dot" style:background={b.color}></span>{/snippet}
            {b.label}
            {#snippet trailing()}<span class="nav-count">{b.count}</span>{/snippet}
          </SidebarNavItem>
        {/each}
      </SidebarGroup>
    {/if}
  </SidebarNav>

  <!-- ── MAIN ── -->
  <main class="main">
    <header class="main-head">
      <h1>Welcome back, {firstName}</h1>
      <p class="sub" aria-live="polite">
        {#if reviewJobs.length}
          <strong class="s-hot"
            >{reviewJobs.length}
            {reviewJobs.length === 1 ? "study is" : "studies are"} ready to review</strong
          >
        {:else}
          <strong>You're all caught up</strong>
        {/if}
        {#if summaryTail}<span class="s-dim">· {summaryTail}</span>{/if}
        {#if failedJobs.length}<span class="s-alert">· {failedJobs.length} failed</span>{/if}
      </p>
    </header>

    {#if tab === "research"}
      {#if data.loadError && jobs.length === 0}
        <!-- Backend failed to load — history is NOT gone. Distinct from empty. -->
        <div class="state-panel state-error">
          <div class="state-icon state-icon-error"><AlertTriangle size={30} aria-hidden="true" /></div>
          <h2>Couldn't load your research</h2>
          <p>
            Something went wrong reaching the server. Your research isn't lost — this is
            just a loading problem. Try again in a moment.
          </p>
          <button class="btn-secondary" onclick={() => location.reload()} type="button">
            <RotateCw size={16} aria-hidden="true" /> Retry
          </button>
        </div>
      {:else if jobs.length === 0}
        <div class="state-panel">
          <div class="state-icon state-icon-accent"><Search size={30} aria-hidden="true" /></div>
          <h2>No research yet</h2>
          <p>
            NicheIQ analyzes Reddit and Hacker News discussions, identifies pain points,
            and generates a comprehensive market research report — first ideas in ~15
            minutes.
          </p>
          <a class="btn-primary btn-lg" href="/new"><Plus size={17} aria-hidden="true" /> Start your first research</a>
          <p class="state-foot">Two-phase AI research with your input at the gate. ~35 minutes total.</p>
        </div>
      {:else}
        <!-- Search -->
        <div class="dashboard-toolbar">
          <div class="search-field">
            <Search class="search-ic" size={16} aria-hidden="true" />
            <input
              type="text"
              bind:this={searchInput}
              bind:value={searchQuery}
              placeholder="Search research…"
              aria-label="Search research"
            />
            {#if searchQuery}
              <button class="search-clear" type="button" onclick={() => (searchQuery = "")} aria-label="Clear search">
                <XCircle size={15} aria-hidden="true" />
              </button>
            {:else}
              <kbd class="search-kbd" aria-hidden="true">/</kbd>
            {/if}
          </div>
          {#if q && hasAnyVisible}
            <span class="search-count">{buckets[0].count} {buckets[0].count === 1 ? "result" : "results"}</span>
          {:else}
            <span class="search-context">Filter by niche or project name</span>
          {/if}
        </div>

        {#if q && !hasAnyVisible}
          <p class="filter-empty">No research matches "{searchQuery}".</p>
        {:else}
          <!-- ══ READY TO REVIEW (positive: ideas ready → pick for deep research) ══ -->
          {#if show("review") && fReview.length}
            <section class="group">
              <div class="group-head">
                <h2>Ready to review</h2>
                <span class="group-meta">pick candidates for deep research</span>
              </div>
              <div class="list list--ready">
                <div class="list-head" aria-hidden="true">
                  <span></span>
                  <span>Study</span>
                  <span>Ideas</span>
                  <span>Action</span>
                </div>
                {#each fReview as job (job.id)}
                  {@const atGate = job.status.toUpperCase() === "AWAITING_GATE"}
                  <a class="row row-link" href="/jobs/{job.id}">
                    <span class="row-dot" style:background="var(--color-accent)"></span>
                    <h3 class="row-title">{job.niche}</h3>
                    <span class="row-meta">
                      {#if atGate}Checkpoint reached{:else if job.solutionIdeasCount}<strong>{job.solutionIdeasCount} ideas</strong> ready{:else}Ideas ready{/if}
                      <span class="row-dim">· {ago(job.createdAt)}</span>
                    </span>
                    <span class="row-cta">{atGate ? "Review checkpoint" : "Choose ideas"} <ArrowRight size={14} aria-hidden="true" /></span>
                  </a>
                {/each}
              </div>
            </section>
          {/if}

          <!-- ══ IN PROGRESS ══ -->
          {#if show("progress") && fProgress.length}
            <section class="group">
              <div class="group-head">
                <h2>In progress</h2>
                <span class="group-meta">research underway</span>
              </div>
              <div class="list">
                {#each fProgress as job (job.id)}
                  {@const meta = statusMeta(job.status)}
                  {@const counts = getAdjustedStageCounts(job)}
                  <div class="row">
                    <span class="row-dot" class:row-dot-live={isLive(job.status)} style:--rail={meta.color} style:background={meta.color}></span>
                    <div class="row-main">
                      <h3 class="row-title">{job.niche}</h3>
                      {#if job.status === "RUNNING" || job.status === "RUNNING_PHASE2"}
                        <div class="row-prog">
                          <div
                            class="prog-bar"
                            role="progressbar"
                            aria-valuenow={Math.round(job.progressPercent ?? 0)}
                            aria-valuemin="0"
                            aria-valuemax="100"
                            aria-label="Research progress for {job.niche}"
                          ><span style:width="{job.progressPercent ?? 0}%" style:background={meta.color}></span></div>
                          <span class="row-sub row-dim">{job.currentStageName ?? meta.label}{#if counts.total} · {counts.completed}/{counts.total}{/if}</span>
                        </div>
                      {:else if job.status === "REGENERATING"}
                        <p class="row-sub row-dim"><Loader2 size={13} class="spinner" aria-hidden="true" /> Generating a fresh batch of ideas…</p>
                      {:else}
                        <p class="row-sub row-dim">{#if job.queuePosition}Position {job.queuePosition} in queue{:else}Preparing to start…{/if}</p>
                      {/if}
                    </div>
                    <div class="row-end">
                      <span class="row-badge" style:color={meta.color}>{meta.label}</span>
                      <button class="link-cancel" type="button" onclick={() => cancelJob(job)} disabled={cancellingJobs.has(job.id)}>
                        {cancellingJobs.has(job.id) ? "Cancelling…" : "Cancel"}
                      </button>
                    </div>
                  </div>
                {/each}
              </div>
            </section>
          {/if}

          <!-- ══ COMPLETED ══ -->
          {#if show("done") && fDone.length}
            <section class="group">
              <div class="group-head">
                <h2>Completed</h2>
                <span class="group-meta">open to read the full report</span>
              </div>
              <div class="list">
                {#each visibleDone as job (job.id)}
                  {@const s = summaries[job.id]}
                  {@const opp = toScore100(s?.opportunity_score)}
                  {@const fit = toScore100(s?.market_fit_score)}
                  {@const feas = toScore100(s?.technical_feasibility_score)}
                  <a class="row row-link" href={reportHref(job)}>
                    <span class="row-dot" style:background="var(--color-success-text)"></span>
                    <div class="row-main">
                      <h3 class="row-title">{s?.solution_name ?? job.niche}</h3>
                      {#if s?.solution_tagline && s.solution_tagline !== s.solution_name}
                        <p class="row-sub row-dim">{s.solution_tagline}</p>
                      {/if}
                    </div>
                    <div class="row-end">
                      {#if fit != null || feas != null || opp != null}
                        <span class="dfo">
                          {#if fit != null}<span class="dfo-item">Fit <b style:color={scoreColor(fit)}>{fit}</b></span>{/if}
                          {#if feas != null}<span class="dfo-item">Feas <b style:color={scoreColor(feas)}>{feas}</b></span>{/if}
                          {#if opp != null}<span class="dfo-item">Opp <b style:color={scoreColor(opp)}>{opp}</b></span>{/if}
                        </span>
                      {/if}
                      {#if s?.verdict}<span class="row-badge" style:color={verdictColor(s.verdict)}>{s.verdict}</span>{/if}
                      <span class="row-cta">Open <ArrowRight size={14} aria-hidden="true" /></span>
                    </div>
                  </a>
                {/each}
              </div>
              {#if hasMoreDone}
                <button class="show-more" type="button" onclick={toggleAllCompleted}>
                  <ChevronDown size={15} class={showAllCompleted ? "chev chev-open" : "chev"} aria-hidden="true" />
                  {showAllCompleted ? "Show less" : `Show ${fDone.length - INITIAL_VISIBLE_COMPLETED} more completed`}
                </button>
              {/if}
            </section>
          {/if}

          <!-- ══ FAILED (hard, resumable errors — kept apart from Ready to review) ══ -->
          {#if show("failed") && fFailed.length}
            <section class="group">
              <div class="group-head">
                <h2>Failed</h2>
                <span class="group-meta">resume from a checkpoint</span>
              </div>
              <div class="list">
                {#each fFailed as job (job.id)}
                  <div class="row">
                    <span class="row-dot" style:background="var(--color-error-text)"></span>
                    <h3 class="row-title">{job.niche}</h3>
                    <span class="row-meta">
                      <span class="row-fail">Failed</span>{#if job.creditRefunded}<span class="row-dim"> · refunded</span>{/if}
                    </span>
                    <button class="btn-ghost btn-xs" type="button" onclick={() => resumeJob(job)} disabled={resumingJobs.has(job.id)}>
                      {#if resumingJobs.has(job.id)}
                        <Loader2 size={13} class="spinner" aria-hidden="true" /> Resuming…
                      {:else}
                        <RotateCcw size={13} aria-hidden="true" /> Resume
                      {/if}
                    </button>
                  </div>
                {/each}
              </div>
            </section>
          {/if}

          <!-- ══ ARCHIVED ══ -->
          {#if show("archived") && fArchived.length}
            <section class="group">
              <button class="group-head group-toggle" type="button" onclick={() => (archivedOpen = !archivedOpen)} aria-expanded={archivedShown} aria-controls="archived-list">
                <h2>Archived</h2>
                <span class="group-meta">
                  {fArchived.length} cancelled or gated
                  <ChevronDown size={15} class={archivedShown ? "chev chev-open" : "chev"} aria-hidden="true" />
                </span>
              </button>
              {#if archivedShown}
                <div class="list" id="archived-list">
                  {#each fArchived as job (job.id)}
                    {@const meta = statusMeta(job.status)}
                    {@const gated = job.status.toUpperCase() === "FAILED"}
                    {@const col = gated ? "var(--color-warning-text)" : meta.color}
                    <div class="row">
                      <span class="row-dot" style:background={col}></span>
                      <div class="row-main">
                        <h3 class="row-title">{job.niche}</h3>
                        <p class="row-sub row-dim">
                          {gated ? "Quality gate" : "Cancelled"}{#if job.creditRefunded} · credit refunded{/if}{#if gated && job.stopReasonDetails?.recommendation} · {job.stopReasonDetails.recommendation}{/if}
                        </p>
                      </div>
                      <a class="row-cta row-cta-muted" href={rerunHref(job.niche)}>
                        {gated ? "Try broader niche" : "Run again"} <ArrowRight size={13} aria-hidden="true" />
                      </a>
                    </div>
                  {/each}
                </div>
              {/if}
            </section>
          {/if}

          {#if filter !== "all" && (buckets.find((b) => b.key === filter)?.count ?? 0) === 0}
            <p class="filter-empty">Nothing in this group right now.</p>
          {/if}
        {/if}
      {/if}
    {:else}
      <!-- ══════════ SAVED TAB ══════════ -->
      {#if savedTotal === 0}
        <div class="state-panel">
          <div class="state-icon state-icon-accent"><Bookmark size={28} aria-hidden="true" /></div>
          <h2>Nothing saved yet</h2>
          <p>
            Bookmark ideas and pain points from any report or the catalog and they'll
            collect here — your running research docket.
          </p>
          <a class="btn-primary btn-lg" href="/ideas"><ArrowRight size={17} aria-hidden="true" /> Browse the catalog</a>
        </div>
      {:else}
        <!-- Saved ideas -->
        <section class="group">
          <div class="group-head">
            <h2>Saved ideas</h2>
            <span class="group-meta">{savedCounts.ideas} kept</span>
          </div>
          {#if savedIdeas.length}
            <ul class="saved-grid">
              {#each savedIdeas as item, i (item.id)}
                <li style="--i: {Math.min(i, 5)}">
                  {#if item.locked}
                    <LockedSavedCard kind="idea" createdAt={item.createdAt} onRemove={() => unsaveIdea(item)} />
                  {:else}
                    <SavedIdeaCard {item} onUnsave={unsaveIdea} onNotesChange={patchIdeaNotes} />
                  {/if}
                </li>
              {/each}
            </ul>
          {:else}
            <p class="filter-empty">No saved ideas yet — bookmark ideas from any report or the catalog.</p>
          {/if}
        </section>

        <!-- Saved pain points -->
        <section class="group">
          <div class="group-head">
            <h2>Saved pain points</h2>
            <span class="group-meta">{savedCounts.painPoints} kept</span>
          </div>
          {#if savedPains.length}
            <SavedPainTable items={savedPains} onUnsave={unsavePain} onNotesChange={patchPainNotes} />
          {:else}
            <p class="filter-empty">No saved pain points.</p>
          {/if}
        </section>

        <a class="docket-link" href="/ideas/saved">
          Manage docket — remix pains into research, filter by notes <ArrowRight size={14} aria-hidden="true" />
        </a>
      {/if}
    {/if}
  </main>
</div>

{#if pendingUndo}
  <UndoToast
    message={pendingUndo.kind === "idea"
      ? `Removed "${pendingUndo.item.idea?.headline ?? pendingUndo.item.idea?.solutionName ?? "idea"}"`
      : `Removed "${pendingUndo.item.painPoint?.title ?? "pain point"}"`}
    onUndo={undoLast}
    onTimeout={commitUnsave}
  />
{/if}

<style>
  .dash {
    display: grid;
    grid-template-columns: 300px 1fr;
    min-height: calc(100dvh - 3.5rem);
    background: var(--color-bg-base);
    font-family: var(--font-body);
    color: var(--color-text-secondary);
  }

  /* ── SIDEBAR slot content (dot + count); shell/rows come from the shared
       sidebar primitives (SidebarNav / SidebarGroup / SidebarNavItem). ── */
  .nav-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; margin: 0 5.5px; opacity: 0.68; }
  :global(.dash-side .sidebar-nav-item.active) .nav-dot { opacity: 0.82; }
  .nav-count {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 600;
    color: var(--color-text-muted);
    font-variant-numeric: tabular-nums;
  }
  :global(.dash-side .sidebar-nav-item.active) .nav-count { color: var(--color-text-primary); }

  /* ── MAIN ── */
  .main {
    width: min(76rem, 100%);
    margin: 0 auto;
    padding: 2rem 2.5rem 5rem;
    min-width: 0;
  }
  .main-head { margin-bottom: 1.55rem; }
  .main-head h1 {
    margin: 0;
    font-family: var(--font-display);
    font-size: clamp(1.25rem, 1.72vw, 1.5rem);
    font-weight: 800;
    letter-spacing: -0.01em;
    line-height: 1.13;
    color: var(--color-text-primary);
  }
  .sub { margin: 0.38rem 0 0; font-size: 0.9375rem; color: var(--color-text-muted); max-width: 44rem; }
  .s-hot { color: var(--color-accent-hover); font-weight: 700; }
  .s-dim { color: var(--color-text-muted); font-variant-numeric: tabular-nums; }
  .s-alert { color: var(--color-error-text); font-weight: 600; font-variant-numeric: tabular-nums; }

  /* search */
  .dashboard-toolbar {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    margin: 0 0 0.95rem;
    padding-bottom: 0.95rem;
    border-bottom: 1px solid color-mix(in srgb, var(--color-border-emphasis) 38%, transparent);
  }
  .search-field { position: relative; width: min(20rem, 100%); }
  .search-field :global(.search-ic) {
    position: absolute; left: 0.75rem; top: 50%; transform: translateY(-50%);
    color: var(--color-text-muted); pointer-events: none;
  }
  .search-field input {
    width: 100%;
    padding: 0.5rem 2.2rem 0.5rem 2.25rem;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-bg-elevated);
    font-family: var(--font-body);
    font-size: 0.875rem;
    color: var(--color-text-primary);
    transition: border-color 0.15s ease;
  }
  .search-field input:hover { border-color: var(--color-border-emphasis); }
  .search-field input:focus-visible { outline: 2px solid var(--color-accent); outline-offset: -1px; border-color: transparent; }
  .search-clear {
    position: absolute; right: 0.375rem; top: 50%; transform: translateY(-50%);
    /* padding + negative margin grows the tap target to ≥24px without moving it */
    padding: 0.3rem; border-radius: 4px;
    background: none; border: none; color: var(--color-text-muted); cursor: pointer;
    display: inline-flex; align-items: center; justify-content: center;
    transition: color 0.12s ease, background 0.12s ease;
  }
  .search-clear:hover { color: var(--color-text-primary); background: var(--color-bg-surface); }
  .search-clear:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 1px; }
  .search-kbd {
    position: absolute; right: 0.6rem; top: 50%; transform: translateY(-50%);
    display: inline-flex; align-items: center; justify-content: center;
    width: 1.15rem; height: 1.15rem;
    font-family: var(--font-mono); font-size: 0.625rem; color: var(--color-text-muted);
    background: var(--color-bg-surface); border: 1px solid var(--color-border); border-radius: 4px;
  }
  .search-count,
  .search-context {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    white-space: nowrap;
  }

  /* groups */
  .group { margin-bottom: 1.45rem; }
  .group-head {
    display: flex; align-items: baseline; justify-content: space-between;
    gap: var(--space-4); margin-bottom: 0.68rem; width: 100%;
  }
  .group-head h2 { margin: 0; font-family: var(--font-display); font-size: 1rem; font-weight: 700; color: var(--color-text-primary); }
  .group-meta {
    font-family: var(--font-mono); font-size: 0.6875rem; text-transform: uppercase;
    letter-spacing: 0.05em; color: var(--color-text-muted);
    display: inline-flex; align-items: center; gap: 0.4rem;
  }
  .group-toggle { background: none; border: none; cursor: pointer; text-align: left; padding: 0; }
  .group-toggle:hover .group-meta { color: var(--color-text-primary); }
  .group-toggle:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 3px; border-radius: var(--radius-sm); }
  .group-toggle :global(.chev) { transition: transform 0.15s ease; }
  .group-toggle :global(.chev-open) { transform: rotate(180deg); }

  /* ── list panel (job-page table idiom: ONE bordered panel, hairline rows —
       not a stack of identical drop-shadow cards) ── */
  .list {
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 52%, transparent);
    border-radius: var(--radius-lg);
    background: var(--color-bg-elevated);
    overflow: hidden;
    box-shadow:
      var(--shadow-sm),
      inset 0 1px 0 color-mix(in srgb, white 72%, transparent);
  }
  .list-head,
  .row {
    display: grid;
    grid-template-columns: 0.45rem minmax(0, 1fr) minmax(10rem, max-content) minmax(4.6rem, max-content);
    align-items: center;
    gap: 0.82rem;
  }
  .list-head {
    padding: 0.48rem 1rem;
    border-bottom: 1px solid color-mix(in srgb, var(--color-border-emphasis) 42%, transparent);
    background: color-mix(in srgb, var(--color-bg-surface) 74%, var(--color-bg-elevated));
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    line-height: 1;
    text-transform: uppercase;
  }
  .list-head span:nth-child(3),
  .list-head span:nth-child(4) { justify-self: end; }
  .row {
    padding: 0.66rem 1rem;
    border-bottom: 1px solid var(--color-border);
    text-decoration: none;
    transition: background-color 180ms cubic-bezier(0.32, 0.72, 0, 1);
  }
  .row:last-child { border-bottom: none; }
  .row-link { cursor: pointer; }
  .row-link:hover { background: var(--color-bg-surface); }
  .row-link:active { background: var(--color-bg-hover); }
  .row-link:focus-visible { outline: 2px solid var(--color-accent); outline-offset: -2px; }

  .row-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
  .row-dot-live {
    box-shadow: 0 0 0 0 color-mix(in srgb, var(--rail) 50%, transparent);
    animation: dot-pulse 2s infinite;
  }
  @keyframes dot-pulse {
    0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--rail) 45%, transparent); }
    70% { box-shadow: 0 0 0 6px transparent; }
    100% { box-shadow: 0 0 0 0 transparent; }
  }

  .row-main { grid-column: 2; min-width: 0; }
  .row-title {
    grid-column: 2; min-width: 0;
    margin: 0; font-size: 0.875rem; font-weight: 700; color: var(--color-text-primary);
    line-height: 1.28; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  /* Right-aligned meta column on single-line rows — gives the row a table-like
     structure (title | meta | action) instead of a title-left / cta-right void. */
  .row-meta {
    grid-column: 3;
    justify-self: end;
    display: inline-flex; align-items: baseline; gap: 0.25rem; flex-shrink: 0;
    font-size: 0.8125rem; color: var(--color-text-secondary); white-space: nowrap;
  }
  .row-meta strong { color: var(--color-text-primary); font-weight: 700; }
  .row-sub {
    margin: 0.14rem 0 0; font-size: 0.75rem; color: var(--color-text-secondary); line-height: 1.4;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    display: flex; align-items: center; gap: 0.3rem; min-width: 0;
  }
  .row-dim { color: var(--color-text-muted); font-weight: 400; min-width: 0; overflow: hidden; text-overflow: ellipsis; }
  .row-fail { color: var(--color-error-text); font-weight: 600; flex-shrink: 0; }

  .row-end {
    grid-column: 3 / -1;
    justify-self: end;
    display: inline-flex;
    align-items: center;
    gap: var(--space-4);
    flex-shrink: 0;
  }
  .row-cta {
    grid-column: 4;
    justify-self: end;
    display: inline-flex; align-items: center; gap: 0.25rem; flex-shrink: 0;
    font-size: 0.8125rem; font-weight: 700; color: var(--color-accent-dark); white-space: nowrap;
    transition: color 0.13s ease;
  }
  .row-link:hover .row-cta,
  .row-link:focus-visible .row-cta { color: var(--color-accent-hover); }
  .row-cta-muted {
    color: var(--color-text-secondary); font-family: var(--font-mono);
    font-size: 0.75rem; font-weight: 500; transition: color 0.12s ease;
  }
  .row-cta-muted:hover { color: var(--color-text-primary); }
  .row-cta-muted:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; border-radius: 3px; }
  .row-badge {
    display: inline-flex; align-items: center; flex-shrink: 0;
    font-size: 0.625rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em;
    padding: 0.15rem 0.45rem; border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, currentColor 40%, transparent);
  }

  /* progress row second line: thin bar + stage */
  .row-prog { margin-top: 0.35rem; }
  .prog-bar { height: 4px; border-radius: 3px; background: var(--color-bg-surface); overflow: hidden; }
  .prog-bar span { display: block; height: 100%; border-radius: 3px; transition: width 0.4s ease; }
  .row-prog .row-sub { margin-top: 0.3rem; }
  .row-sub :global(.spinner) { color: var(--color-warning-text); animation: spin 1s linear infinite; flex-shrink: 0; }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* completed scores */
  .dfo {
    display: inline-flex; align-items: center; gap: var(--space-3);
    font-family: var(--font-mono); font-size: 0.6875rem; text-transform: uppercase; letter-spacing: 0.03em;
    color: var(--color-text-muted);
  }
  .dfo-item b { font-weight: 700; font-size: 0.75rem; font-variant-numeric: tabular-nums; }

  .link-cancel {
    background: none; border: none; cursor: pointer;
    font-family: var(--font-mono); font-size: 0.6875rem; color: var(--color-text-muted);
    /* padding+neg-margin → ≥24px tap target; min-width holds "Cancel"↔"Cancelling…" steady */
    padding: 0.3rem 0.4rem; margin: -0.3rem -0.4rem;
    min-width: 5.5rem; text-align: right;
    transition: color 0.12s ease, opacity 0.12s ease;
  }
  .link-cancel:hover:not(:disabled) { color: var(--color-error-text); }
  .link-cancel:active:not(:disabled) { opacity: 0.7; }
  .link-cancel:disabled { opacity: 0.6; cursor: default; }
  .link-cancel:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; border-radius: 3px; }

  /* .btn-ghost is the global v3 ghost recipe (components.css); this page only
     adds the states/sizing it doesn't define yet. */
  .btn-ghost:active:not(:disabled) { transform: scale(0.98); }
  .btn-ghost:disabled { opacity: 0.6; cursor: default; }
  .btn-ghost:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  /* min-width holds "Resume"↔"Resuming…" steady (no width jump on click) */
  .btn-xs { padding: 0.3rem 0.6rem; font-size: 0.75rem; min-width: 6rem; }
  .btn-ghost :global(.spinner) { animation: spin 1s linear infinite; }

  .show-more {
    width: 100%; margin-top: var(--space-3); padding: var(--space-3);
    display: inline-flex; align-items: center; justify-content: center; gap: 0.4rem;
    border: 1px solid var(--color-border); border-radius: var(--radius-lg);
    background: var(--color-bg-surface); color: var(--color-text-secondary);
    font-size: 0.8125rem; font-weight: 600; cursor: pointer;
    transition: background 0.15s ease, color 0.15s ease;
  }
  .show-more:hover { background: var(--color-bg-hover); color: var(--color-text-primary); }
  .show-more:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  .show-more :global(.chev) { transition: transform 0.15s ease; }
  .show-more :global(.chev-open) { transform: rotate(180deg); }

  /* saved tab */
  .saved-grid {
    display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--space-4);
    list-style: none; margin: 0; padding: 0;
  }
  .docket-link {
    display: inline-flex; align-items: center; gap: 0.4rem;
    font-family: var(--font-mono); font-size: 0.75rem; color: var(--color-text-secondary);
    transition: color 0.12s ease;
  }
  .docket-link:hover { color: var(--color-accent-hover); }
  .docket-link:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; border-radius: 3px; }

  .filter-empty { font-size: 0.875rem; color: var(--color-text-muted); padding: var(--space-6) 0; }

  /* state panels (empty / error) */
  .state-panel {
    text-align: center; padding: var(--space-16) var(--space-6);
    border: 1px solid var(--color-border); border-radius: var(--radius-xl);
    background: var(--color-bg-elevated);
  }
  .state-error { border-color: color-mix(in srgb, var(--color-error-text) 30%, var(--color-border)); background: color-mix(in srgb, var(--color-error-text) 4%, var(--color-bg-elevated)); }
  .state-icon {
    width: 4rem; height: 4rem; margin: 0 auto var(--space-5);
    display: grid; place-items: center; border-radius: var(--radius-xl);
  }
  .state-icon-accent { background: var(--color-accent-subtle); border: 1px solid var(--color-border-accent); color: var(--color-accent); }
  .state-icon-error { background: color-mix(in srgb, var(--color-error-text) 10%, transparent); border: 1px solid color-mix(in srgb, var(--color-error-text) 25%, transparent); color: var(--color-error-text); }
  .state-panel h2 { margin: 0 0 var(--space-2); font-family: var(--font-display); font-size: 1.375rem; font-weight: 700; color: var(--color-text-primary); }
  .state-panel p { margin: 0 auto var(--space-6); max-width: 46ch; font-size: 0.9375rem; line-height: 1.6; color: var(--color-text-secondary); }
  .state-panel .btn-primary, .state-panel .btn-secondary { margin: 0 auto; }
  .state-foot { margin-top: var(--space-4) !important; font-size: 0.75rem !important; color: var(--color-text-muted) !important; }

  /* ── responsive: sidebar → top bar ── */
  @media (max-width: 900px) {
    .dash { grid-template-columns: 1fr; }
    :global(.dash-side.sidebar-nav) {
      position: static; height: auto; border-right: none;
      border-bottom: 1px solid var(--color-border);
      padding: 1.25rem 1.25rem 1rem;
      gap: 0.75rem;
    }
    /* On mobile each group becomes a horizontally-scrollable row of chips. */
    :global(.dash-side .sidebar-nav-group) {
      flex-direction: row; align-items: center; gap: 0.5rem; overflow-x: auto;
    }
    :global(.dash-side .sidebar-nav-group-head),
    :global(.dash-side .sidebar-nav-divider) { display: none; }
    :global(.dash-side .sidebar-nav-item) {
      width: auto; white-space: nowrap; padding: 0.4rem 0.8rem;
      border: 1px solid var(--color-border); border-radius: var(--radius-md);
      background: var(--color-bg-elevated);
    }
    :global(.dash-side .sidebar-nav-item.active) { background: var(--color-accent-subtle); border-color: var(--color-border-accent); }
    :global(.dash-side .sidebar-nav-item.active)::before { display: none; }
    .main { width: 100%; padding: var(--space-6) var(--space-5) var(--space-12); }
    .dashboard-toolbar { flex-wrap: wrap; }
    .saved-grid { grid-template-columns: 1fr; }
  }
  @media (max-width: 640px) {
    .list-head { display: none; }
    .row {
      display: flex;
      align-items: flex-start;
      flex-wrap: wrap;
      padding: 0.8rem var(--space-4);
    }
    .row-title {
      flex-basis: calc(100% - 1.5rem);
      white-space: normal;
      overflow: visible;
      text-overflow: clip;
    }
    .row-main {
      flex-basis: calc(100% - 1.5rem);
    }
    .row-meta,
    .row-end {
      margin-left: calc(8px + var(--space-3));
      flex-wrap: wrap;
      justify-content: flex-start;
      gap: var(--space-2);
      min-width: 0;
    }
    .row-sub {
      white-space: normal;
    }
    .dfo {
      flex-wrap: wrap;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .row-dot-live, .row-sub :global(.spinner), .btn-ghost :global(.spinner), .prog-bar span { animation: none !important; transition: none !important; }
  }
</style>
