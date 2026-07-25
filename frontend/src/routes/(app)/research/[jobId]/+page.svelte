<script lang="ts">
  // Chat-first guided-research lifecycle page (EXPERIMENTAL, admin-gated).
  // The analyst ledger is the page's spine: past checkpoints collapse above
  // whatever the run needs now — the GateWorkbench at checkpoints, the live
  // run shell while stages execute, the closed transcript once terminal.
  // Selection still deep-links to the production workbench (its candidate
  // table + tray + votes are a page of their own); everything else lives here.
  import { page } from "$app/state";
  import { getJob, subscribeToProgress, type Job } from "$lib/api";
  import { chatLedger } from "$lib/stores/chatLedger.svelte";
  import SegmentedLedger from "$lib/components/chat/SegmentedLedger.svelte";
  import GateWorkbench from "$lib/components/gate/GateWorkbench.svelte";
  import ResearchProgressScreen from "$lib/components/preview/ResearchProgressScreen.svelte";
  import { ArrowRight, Loader2 } from "lucide-svelte";

  const jobId = $derived(page.params.jobId ?? "");

  let job = $state<Job | null>(null);
  let loadError = $state("");
  // Mirrors the production job page: apply_stay round-trips pass through
  // QUEUED/RUNNING but must keep the gate mounted until the SAME gate
  // re-arrives with a refreshed artifact.
  let gateApplyPending = $state(false);
  let lastHandledStatus = $state<string | null>(null);
  let closeSSE: (() => void) | null = null;

  const TERMINAL = ["COMPLETED", "FAILED", "CANCELLED"];

  const isGatePhase = $derived(
    job?.status === "AWAITING_GATE" ||
      (gateApplyPending && ["QUEUED", "RUNNING"].includes(job?.status ?? "")),
  );
  const isSelectionPhase = $derived(
    ["AWAITING_SELECTION", "REGENERATING"].includes(job?.status ?? ""),
  );
  const isTerminal = $derived(TERMINAL.includes(job?.status ?? ""));
  const isWorking = $derived(!!job && !isGatePhase && !isSelectionPhase && !isTerminal);
  const workingPhase = $derived(job?.status === "RUNNING_PHASE2" ? "deep_research" : "discovery");

  function handleUpdate(next: Job) {
    const prev = job?.status;
    job = next;
    if (next.status !== prev && next.status !== lastHandledStatus) {
      lastHandledStatus = next.status;
      // New checkpoint or selection arrival → fresh history (opening message,
      // persisted rows); also clears the apply-pending override on re-arrival.
      if (next.status === "AWAITING_GATE" || next.status === "AWAITING_SELECTION") {
        gateApplyPending = false;
        void chatLedger.reload();
      }
      if (TERMINAL.includes(next.status)) {
        closeSSE?.();
        closeSSE = null;
        void chatLedger.reload();
      }
    }
  }

  $effect(() => {
    const id = jobId;
    if (!id) return;
    void chatLedger.init(id);
    getJob(id)
      .then((j) => {
        job = j;
        lastHandledStatus = j.status;
        if (!TERMINAL.includes(j.status)) {
          closeSSE = subscribeToProgress(id, handleUpdate);
        }
      })
      .catch(() => {
        loadError = "Couldn't load this research run — it may not exist or belong to another account.";
      });
    return () => {
      closeSSE?.();
      closeSSE = null;
    };
  });

  // ── Boundary markers (Phase 1: synthesized from lifecycle position; Phase 3
  //    replaces these with worker-persisted rows). markers[stage] renders AFTER
  //    that segment's collapsed row. ──
  const passedG1 = $derived(!!job && (job.gateStage !== 1 || job.status !== "AWAITING_GATE") && chatLedger.segmentMessages(1).length > 0);
  const reachedG2OrLater = $derived(
    !!job &&
      (job.status === "AWAITING_SELECTION" ||
        job.status === "REGENERATING" ||
        job.status === "RUNNING_PHASE2" ||
        job.status === "COMPLETED" ||
        (job.status === "AWAITING_GATE" && job.gateStage === 4)),
  );
  const boundaryMarkers = $derived.by(() => {
    const m: Record<number, string> = {};
    if (passedG1 && reachedG2OrLater) m[1] = "Evidence search complete — audience and pains mapped";
    if (chatLedger.segmentMessages(4).length > 0 && (isSelectionPhase || job?.status === "RUNNING_PHASE2" || job?.status === "COMPLETED")) {
      m[4] = "Idea generation complete — candidates ranked";
    }
    if (chatLedger.segmentMessages(5).length > 0 && job?.status === "COMPLETED") {
      m[5] = "Deep research complete — report ready";
    }
    return m;
  });

  const nicheTitle = $derived(job?.niche ? (job.niche.length > 80 ? job.niche.slice(0, 80) + "…" : job.niche) : "Research");
  const userEmail = $derived(page.data.session?.user?.email ?? null);
</script>

<svelte:head>
  <title>{nicheTitle} - Guided research - NicheIQ</title>
</svelte:head>

<div class="research-page" class:research-page--working={isWorking}>
  {#if loadError}
    <div class="research-error" role="alert">
      <p>{loadError}</p>
      <div class="research-error-actions">
        <button type="button" class="research-retry" onclick={() => location.reload()}>Try again</button>
        <a href="/dashboard">Back to Dashboard</a>
      </div>
    </div>
  {:else if !job}
    <div class="research-loading">
      <Loader2 class="w-8 h-8 animate-spin" aria-hidden="true" />
      <p>Loading research&hellip;</p>
    </div>
  {:else}
    <header class="research-head">
      <nav class="research-crumb" aria-label="Breadcrumb">
        <a href="/dashboard">Dashboard</a>
        <span aria-hidden="true">&rsaquo;</span>
        <span aria-current="page">Guided research</span>
      </nav>
      <h1 class="research-title">{nicheTitle}</h1>
    </header>

    {#if isGatePhase && (job.gateStage === 1 || job.gateStage === 4)}
      <!-- Past checkpoints collapse above; the active checkpoint keeps the
           full GateWorkbench (framing document + conversation + Continue). -->
      <SegmentedLedger
        {jobId}
        interactionState="history"
        activeGateStage={job.gateStage}
        {boundaryMarkers}
      />
      <GateWorkbench
        {jobId}
        gateStage={job.gateStage}
        gateArtifact={job.gateArtifact ?? null}
        gateApplyCount={job.gateApplyCount ?? 0}
        gateReachedAt={job.gateReachedAt ?? null}
        jobStatus={job.status}
        guidedCosts={page.data.stageCosts?.guided ?? null}
        onContinueStart={() => {
          job = { ...job!, status: "QUEUED" };
        }}
        onApplyStayStart={() => {
          gateApplyPending = true;
        }}
        onApplyStayError={() => {
          gateApplyPending = false;
        }}
      />
    {:else if isSelectionPhase}
      <div class="research-selection-card">
        <div>
          <h2>{job.solutionIdeas?.length ? "Candidates are ready" : "Selection checkpoint reached"}</h2>
          <p>
            {#if job.solutionIdeas?.length}
              Discovery ranked {job.solutionIdeas.length} candidates. Review them, ask the analyst, and pick up to 3
              for deep research.
            {:else}
              Discovery reached the selection checkpoint without a ranked shortlist. Open selection to check
              status or regenerate ideas.
            {/if}
          </p>
        </div>
        <a class="research-selection-cta" href="/jobs/{job.id}">
          Open selection
          <ArrowRight class="w-4 h-4" aria-hidden="true" />
        </a>
      </div>
      <SegmentedLedger {jobId} interactionState="history" activeGateStage={5} {boundaryMarkers} />
    {:else if isWorking}
      <!-- Run shell: focused progress column + the ledger, working state. -->
      <div class="run-shell">
        <div class="run-shell-main">
          <ResearchProgressScreen
            {jobId}
            phase={workingPhase}
            jobStatus={job.status}
            embedded
            niche={job.niche}
            entryMode={job.entryMode}
            {userEmail}
            progressPercent={job.progressPercent ?? 0}
            stagesCompleted={job.stagesCompleted ?? 0}
            totalStages={job.totalStages ?? 0}
            currentStage={job.currentStage ?? 0}
            currentStageName={job.currentStageName}
            queuePosition={job.queuePosition ?? undefined}
            selectedNames={job.selectedSolutions ?? []}
            selectedItems={job.selectionDraft?.items ?? []}
            solutionIdeas={job.solutionIdeas ?? []}
            primaryWinner={job.selectedSolution}
          />
        </div>
        <div class="run-shell-rail">
          <SegmentedLedger
            {jobId}
            interactionState="working"
            jobStatus={job.status}
            currentStageName={job.currentStageName}
            currentStage={job.currentStage}
            stagesCompleted={job.stagesCompleted}
            totalStages={job.totalStages}
            progressPercent={job.progressPercent}
            queuePosition={job.queuePosition}
            {boundaryMarkers}
          />
        </div>
      </div>
    {:else}
      <!-- Terminal: COMPLETED / FAILED / CANCELLED -->
      <div class="research-terminal">
        {#if job.status === "COMPLETED"}
          <div class="research-terminal-card">
            <div>
              <h2>Research complete</h2>
              <p>The full report is ready — the conversation below is the record of how it got there.</p>
            </div>
            <a class="research-selection-cta" href="/jobs/{job.id}/report">
              View report
              <ArrowRight class="w-4 h-4" aria-hidden="true" />
            </a>
          </div>
        {:else if job.status === "FAILED"}
          <div class="research-terminal-card research-terminal-card--failed">
            <div>
              <h2>Research stopped</h2>
              <p>{job.errorDetails?.userMessage ?? job.errorMessage ?? "The run failed."} Resume it from the job page.</p>
            </div>
            <a class="research-selection-cta" href="/jobs/{job.id}">
              Open job page
              <ArrowRight class="w-4 h-4" aria-hidden="true" />
            </a>
          </div>
        {:else}
          <div class="research-terminal-card">
            <div>
              <h2>Research cancelled</h2>
              <p>Credits were refunded. Start a new run whenever you're ready.</p>
            </div>
            <a class="research-selection-cta" href="/research">
              New research
              <ArrowRight class="w-4 h-4" aria-hidden="true" />
            </a>
          </div>
        {/if}
        <SegmentedLedger {jobId} interactionState="readonly" {boundaryMarkers} />
      </div>
    {/if}
  {/if}
</div>

<style>
  .research-page {
    width: min(48rem, 100%);
    margin: 0 auto;
    padding: 2rem 1.25rem 5rem;
    display: grid;
    gap: var(--space-6);
    align-content: start;
  }
  .research-page--working {
    width: min(72rem, 100%);
  }

  .research-loading,
  .research-error {
    display: grid;
    justify-items: center;
    gap: 0.75rem;
    padding: 4rem 0;
    color: var(--color-text-secondary);
  }
  .research-error-actions {
    display: flex;
    align-items: center;
    gap: var(--space-4);
  }
  .research-retry {
    min-height: 2.25rem;
    padding: 0.45rem 0.9rem;
    background: var(--color-accent-hover);
    border: 1px solid var(--color-accent-hover);
    border-radius: var(--radius-md);
    color: var(--color-text-on-accent);
    font-family: var(--font-body);
    font-size: 0.8125rem;
    font-weight: 700;
    cursor: pointer;
    transition: background 150ms var(--ease-out);
  }
  .research-retry:hover {
    background: var(--color-accent-dark);
  }
  .research-retry:active {
    transform: scale(0.98);
  }
  .research-retry:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .research-error a {
    color: var(--color-accent-dark);
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .research-error a:focus-visible,
  .research-crumb a:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
    border-radius: var(--radius-sm);
  }

  .research-head {
    display: grid;
    gap: 0.35rem;
    max-width: 56rem;
  }
  .research-crumb {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }
  .research-crumb a {
    color: var(--color-accent-dark);
    text-decoration: none;
  }
  .research-crumb a:hover {
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .research-title {
    margin: 0;
    font-family: var(--font-display);
    font-size: 1.5rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    line-height: 1.15;
    color: var(--color-text-primary);
  }

  /* ── Run shell: hero column + ledger. Side-by-side on wide screens, stacked
     below that. The ledger is border-only here — the progress hero is flat by
     design and a shadowed card beside it would compete. ── */
  .run-shell {
    display: grid;
    gap: var(--space-6);
  }
  .run-shell-rail :global(.ledger--card) {
    box-shadow: none;
  }
  @media (min-width: 1024px) {
    .run-shell {
      grid-template-columns: minmax(0, 1fr) minmax(20rem, 21.5rem);
      gap: var(--space-6);
      align-items: start;
    }
    .run-shell-rail {
      position: sticky;
      top: 4rem;
      max-height: calc(100dvh - 5rem);
    }
  }

  @media (max-width: 640px) {
    .research-page {
      padding: 1.25rem 1rem 4rem;
      gap: var(--space-5);
    }
    .research-title {
      font-size: 1.35rem;
      text-wrap: balance;
    }
  }

  .research-selection-card,
  .research-terminal-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 1rem;
    padding: var(--space-5);
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-xl);
    box-shadow: var(--shadow-sm);
  }
  .research-terminal-card--failed {
    border-color: color-mix(in srgb, var(--color-error) 25%, transparent);
  }
  .research-selection-card h2,
  .research-terminal-card h2 {
    margin: 0 0 0.25rem;
    font-family: var(--font-display);
    font-size: 1.0625rem;
    font-weight: 700;
    color: var(--color-text-primary);
  }
  .research-selection-card p,
  .research-terminal-card p {
    margin: 0;
    font-size: 0.8125rem;
    line-height: 1.5;
    color: var(--color-text-secondary);
    max-width: 46ch;
  }
  .research-selection-cta {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    min-height: 2.5rem;
    padding: 0.55rem 1rem;
    background: var(--color-accent-hover);
    border: 1px solid var(--color-accent-hover);
    border-radius: var(--radius-md);
    color: var(--color-text-on-accent);
    font-family: var(--font-body);
    font-size: 0.8125rem;
    font-weight: 700;
    text-decoration: none;
    transition: background 150ms ease, transform 150ms ease;
  }
  .research-selection-cta:hover {
    background: var(--color-accent-dark);
  }
  .research-selection-cta:active {
    transform: scale(0.98);
  }
  .research-selection-cta:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .research-terminal {
    display: grid;
    gap: var(--space-6);
  }

  @media (prefers-reduced-motion: reduce) {
    .research-selection-cta,
    .research-retry {
      transition: none;
    }
    .research-selection-cta:active,
    .research-retry:active {
      transform: none;
    }
  }
</style>
