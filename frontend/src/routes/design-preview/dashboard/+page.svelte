<script lang="ts">
  import {
    Plus,
    Compass,
    Check,
    ArrowRight,
    RotateCcw,
    X,
    Bookmark,
    ChevronDown,
    TriangleAlert,
    Loader,
  } from "lucide-svelte";

  /* ────────────────────────────────────────────────────────────
     Prototype — research dashboard redesign on the job-page design
     system. Mock data covers all 9 job statuses so every lifecycle
     treatment is demonstrable; wire to /api/users/:id/jobs later.
     ──────────────────────────────────────────────────────────── */

  type Status =
    | "PENDING" | "QUEUED" | "RUNNING" | "AWAITING_SELECTION"
    | "REGENERATING" | "RUNNING_PHASE2" | "COMPLETED" | "FAILED" | "CANCELLED";

  interface Job {
    id: string;
    niche: string;
    status: Status;
    entryMode: string;
    created: string; // relative
    // running
    progress?: number;
    stage?: string;
    stageIdx?: number;
    stageTotal?: number;
    elapsed?: string;
    // queued
    queuePos?: number;
    // awaiting
    ideaCount?: number;
    // completed
    solutionName?: string;
    tagline?: string;
    verdict?: "Go" | "Conditional" | "No-Go";
    demand?: number;
    feasibility?: number;
    opportunity?: number;
    // failed
    error?: string;
    qualityGate?: boolean;
    creditRefunded?: boolean;
  }

  const user = { firstName: "Alex", credits: 240 };

  const jobs: Job[] = [
    { id: "j1", niche: "Peptides Supplements", status: "AWAITING_SELECTION", entryMode: "Idea", created: "12m ago", ideaCount: 6 },
    { id: "j2", niche: "WADA-safe recovery for tested athletes", status: "FAILED", entryMode: "Pain research", created: "1h ago", error: "OpenAI rate limit hit during pain scoring. Your credits were not charged.", creditRefunded: true },
    { id: "j3", niche: "Home espresso for small kitchens", status: "RUNNING", entryMode: "Discovery", created: "8m ago", progress: 62, stage: "Scoring pain points", stageIdx: 9, stageTotal: 16, elapsed: "8m" },
    { id: "j4", niche: "Break-even beauty spend planning", status: "RUNNING_PHASE2", entryMode: "Idea", created: "40m ago", progress: 34, stage: "Deep research: market sizing", stageIdx: 4, stageTotal: 11, elapsed: "22m" },
    { id: "j5", niche: "Menopause skin-shift routines", status: "REGENERATING", entryMode: "Idea", created: "18m ago" },
    { id: "j6", niche: "Indie game launch marketing", status: "QUEUED", entryMode: "Pain research", created: "3m ago", queuePos: 2 },
    { id: "j7", niche: "Cold plunge for home recovery", status: "PENDING", entryMode: "Idea", created: "1m ago" },
    { id: "j8", niche: "30-plus women anti-aging", status: "COMPLETED", entryMode: "Idea", created: "2d ago",
      solutionName: "Break-Even Clock", tagline: "See when a facelift beats your Botox", verdict: "Conditional", demand: 82, feasibility: 88, opportunity: 80 },
    { id: "j9", niche: "Retinoid adherence", status: "COMPLETED", entryMode: "Discovery", created: "4d ago",
      solutionName: "Retinol Ramp", tagline: "A titration plan that beats the purge", verdict: "Go", demand: 70, feasibility: 79, opportunity: 74 },
    { id: "j10", niche: "Sunscreen habit tracking", status: "COMPLETED", entryMode: "Pain research", created: "6d ago",
      solutionName: "SPF Streak", tagline: "Reapplication nudges tied to local UV", verdict: "No-Go", demand: 58, feasibility: 90, opportunity: 48 },
    { id: "j11", niche: "NFT portfolio analytics", status: "CANCELLED", entryMode: "Idea", created: "1w ago" },
    { id: "j12", niche: "Left-handed calligraphy tools", status: "FAILED", entryMode: "Discovery", created: "5d ago", qualityGate: true, creditRefunded: true, error: "Too few high-severity pains to build a report. Credit refunded — try a broader niche." },
  ];

  interface SavedIdea {
    id: string; name: string; tagline: string; niche: string; verdict: "Go" | "Conditional" | "No-Go"; score: number; note?: string; added: string;
  }
  const savedIdeas: SavedIdea[] = [
    { id: "s1", name: "Shelf Check", tagline: "Flags actives you shouldn't layer from a photo of your shelf", niche: "Skincare · Anti-aging", verdict: "Go", score: 71, note: "Validate the OCR accuracy before committing — the whole wedge is the scan.", added: "2d ago" },
    { id: "s2", name: "Proof Ledger", tagline: "Separate proven actives from hype ingredients", niche: "Skincare · Science", verdict: "Conditional", score: 63, added: "3d ago" },
    { id: "s3", name: "Roster Alert Feed", tagline: "Verified esports roster changes before lineup lock", niche: "Esports · Fantasy", verdict: "Go", score: 66, note: "Cheap to build; check if the data source allows redistribution.", added: "1w ago" },
    { id: "s4", name: "GLP-1 SafeSwitch", tagline: "Compare FDA vs gray-market GLP-1s with safety checklists", niche: "Peptides", verdict: "Conditional", score: 65, added: "1w ago" },
  ];

  interface SavedPain {
    id: string; title: string; niche: string; severity: number; commercialIntent: number; mentions: number;
  }
  const savedPains: SavedPain[] = [
    { id: "p1", title: "Insurance and high cost force patients from branded GLP-1s to gray-market", niche: "Peptides", severity: 80, commercialIntent: 40, mentions: 13 },
    { id: "p2", title: "Athletes risk WADA bans using recovery peptides with no legal alternative", niche: "Peptides", severity: 70, commercialIntent: 40, mentions: 9 },
    { id: "p3", title: "Layering conflicts (retinol + acids) are invisible and quit-inducing", niche: "Skincare", severity: 55, commercialIntent: 35, mentions: 14 },
  ];

  /* ── status config ── */
  const STATUS: Record<Status, { label: string; kind: "attention" | "progress" | "done" | "archived"; color: string; cta: string }> = {
    AWAITING_SELECTION: { label: "Ideas ready", kind: "attention", color: "var(--color-accent)", cta: "Review ideas" },
    FAILED: { label: "Failed", kind: "attention", color: "var(--color-error-text)", cta: "Resume" },
    RUNNING: { label: "Researching", kind: "progress", color: "var(--color-warning-text)", cta: "View progress" },
    RUNNING_PHASE2: { label: "Deep research", kind: "progress", color: "var(--color-warning-text)", cta: "View progress" },
    REGENERATING: { label: "Regenerating ideas", kind: "progress", color: "var(--color-warning-text)", cta: "View" },
    QUEUED: { label: "Queued", kind: "progress", color: "var(--color-info-dark)", cta: "View" },
    PENDING: { label: "Preparing", kind: "progress", color: "var(--color-info-dark)", cta: "View" },
    COMPLETED: { label: "Ready", kind: "done", color: "var(--color-success-text)", cta: "View report" },
    CANCELLED: { label: "Cancelled", kind: "archived", color: "var(--color-text-muted)", cta: "Run again" },
  };
  const isHardFail = (j: Job) => j.status === "FAILED" && !j.qualityGate;
  // pulse only where something is genuinely live: actively computing, or waiting on the user
  const LIVE: Set<Status> = new Set(["AWAITING_SELECTION", "RUNNING", "RUNNING_PHASE2", "REGENERATING"]);
  const isLive = (s: Status) => LIVE.has(s);
  function bucketOf(j: Job): "action" | "progress" | "done" | "archived" {
    if (j.status === "AWAITING_SELECTION" || isHardFail(j)) return "action";
    if (["PENDING", "QUEUED", "RUNNING", "REGENERATING", "RUNNING_PHASE2"].includes(j.status)) return "progress";
    if (j.status === "COMPLETED") return "done";
    return "archived";
  }
  function verdictColor(v: string): string {
    return v === "Go" ? "var(--color-success-text)" : v === "Conditional" ? "var(--color-warning-text)" : "var(--color-error-text)";
  }
  function scoreColor(v: number): string {
    return v >= 60 ? "var(--color-success-text)" : v >= 45 ? "var(--color-warning-text)" : "var(--color-error-text)";
  }

  let tab = $state<"research" | "saved">("research");
  let archivedOpen = $state(false);
  let filter = $state<"all" | "action" | "progress" | "done" | "archived">("all");

  const action = $derived(jobs.filter((j) => bucketOf(j) === "action"));
  const progress = $derived(jobs.filter((j) => bucketOf(j) === "progress"));
  const done = $derived(jobs.filter((j) => bucketOf(j) === "done"));
  const archived = $derived(jobs.filter((j) => bucketOf(j) === "archived"));

  const buckets = $derived([
    { key: "all", label: "All research", count: jobs.length, color: "var(--color-text-muted)" },
    { key: "action", label: "Needs your action", count: action.length, color: "var(--color-accent)" },
    { key: "progress", label: "In progress", count: progress.length, color: "var(--color-warning-text)" },
    { key: "done", label: "Completed", count: done.length, color: "var(--color-success-text)" },
    { key: "archived", label: "Archived", count: archived.length, color: "var(--color-text-muted)" },
  ] as const);
  const show = (b: string) => filter === "all" || filter === b;
  const archivedShown = $derived(archivedOpen || filter === "archived");
  // prefill /new with the niche so a re-run starts pre-loaded
  const rerunHref = (niche: string) => `/new?niche=${encodeURIComponent(niche)}`;
</script>

<div class="page">
  <aside class="sidebar">
    <p class="proto">Prototype · dashboard · <a href="/design-preview">← prototypes</a></p>
    <span class="eyebrow">Your research</span>

    <nav class="side-nav" aria-label="Dashboard views">
      <button class="side-tab" class:side-tab-on={tab === "research"} type="button" onclick={() => (tab = "research")} aria-current={tab === "research" ? "true" : undefined}>
        Research <span class="side-tab-count">{jobs.length}</span>
      </button>
      <button class="side-tab" class:side-tab-on={tab === "saved"} type="button" onclick={() => (tab = "saved")} aria-current={tab === "saved" ? "true" : undefined}>
        Saved ideas <span class="side-tab-count">{savedIdeas.length + savedPains.length}</span>
      </button>
    </nav>

    {#if tab === "research"}
      <span class="side-label">Filter</span>
      <ul class="filter-list">
        {#each buckets as b (b.key)}
          <li>
            <button
              class="filter-row"
              class:filter-on={filter === b.key}
              type="button"
              onclick={() => (filter = b.key)}
              aria-current={filter === b.key ? "true" : undefined}
            >
              <span class="filter-dot" style:background={b.color}></span>
              <span class="filter-label">{b.label}</span>
              <span class="filter-count">{b.count}</span>
            </button>
          </li>
        {/each}
      </ul>
    {/if}

    <div class="side-cta">
      <a class="btn-new" href="/new"><Plus size={16} aria-hidden="true" /> New research</a>
      <p class="side-credits">{user.credits} credits available</p>
    </div>
  </aside>

  <main class="main">
    <header class="main-head">
      <h1>Welcome back, {user.firstName}</h1>
      <p class="sub">
        {#if action.length}<strong class="s-hot">{action.length} {action.length === 1 ? "study needs" : "studies need"} you</strong>{:else}<strong>You're all caught up</strong>{/if}{" "}
        <span class="s-dim">· {progress.length} running · {done.length} completed</span>
      </p>
    </header>

    {#if tab === "research"}
      <!-- ══ NEEDS YOUR ACTION ══ -->
      {#if show("action") && action.length}
        <section class="group">
          <div class="group-head">
            <h2>Needs your action</h2>
            <span class="group-meta">{action.length} waiting on you</span>
          </div>
          <div class="cards">
            {#each action as j (j.id)}
              <article class="job job-attention" style:--rail={STATUS[j.status].color}>
                <div class="job-top">
                  <div class="job-id">
                    <span class="dot" class:dot-pulse={isLive(j.status)} style:background={STATUS[j.status].color}></span>
                    <div>
                      <h3 class="job-title">{j.niche}</h3>
                      <p class="job-meta">{j.entryMode} · {j.created}</p>
                    </div>
                  </div>
                  <span class="badge" style:color={STATUS[j.status].color}>{STATUS[j.status].label}</span>
                </div>

                {#if j.status === "AWAITING_SELECTION"}
                  <div class="action-body">
                    <p class="action-line"><strong>{j.ideaCount} idea candidates</strong> are ready — pick up to 3 to send to deep research.</p>
                    <a class="btn-primary" href="/design-preview/job">{STATUS[j.status].cta} <ArrowRight size={15} aria-hidden="true" /></a>
                  </div>
                {:else if isHardFail(j)}
                  <div class="action-body">
                    <p class="err">{j.error}</p>
                    <div class="err-actions">
                      <a class="btn-primary" href="/new"><RotateCcw size={15} aria-hidden="true" /> {STATUS[j.status].cta}</a>
                      {#if j.creditRefunded}<span class="refund"><Check size={13} aria-hidden="true" /> Credit refunded</span>{/if}
                    </div>
                  </div>
                {/if}
              </article>
            {/each}
          </div>
        </section>
      {/if}

      <!-- ══ IN PROGRESS ══ -->
      {#if show("progress") && progress.length}
        <section class="group">
          <div class="group-head">
            <h2>In progress</h2>
            <span class="group-meta">{progress.length} running</span>
          </div>
          <div class="cards">
            {#each progress as j (j.id)}
              <article class="job" style:--rail={STATUS[j.status].color}>
                <div class="job-top">
                  <div class="job-id">
                    <span class="dot" class:dot-pulse={isLive(j.status)} style:background={STATUS[j.status].color}></span>
                    <div>
                      <h3 class="job-title">{j.niche}</h3>
                      <p class="job-meta">{j.entryMode} · {j.created}{#if j.elapsed} · {j.elapsed} elapsed{/if}</p>
                    </div>
                  </div>
                  <span class="badge" style:color={STATUS[j.status].color}>{STATUS[j.status].label}</span>
                </div>

                {#if j.progress !== undefined}
                  <div class="prog">
                    <div class="prog-bar"><span style:width="{j.progress}%" style:background={STATUS[j.status].color}></span></div>
                    <div class="prog-meta">
                      <span>{j.stage}</span>
                      <span class="prog-count">{j.stageIdx}/{j.stageTotal}</span>
                    </div>
                  </div>
                {:else if j.status === "REGENERATING"}
                  <p class="spin"><Loader size={14} class="spinner" aria-hidden="true" /> Generating a fresh batch of ideas…</p>
                {:else}
                  <p class="queue">{j.queuePos ? `Position ${j.queuePos} in queue` : "Next up"}</p>
                {/if}
              </article>
            {/each}
          </div>
        </section>
      {/if}

      <!-- ══ COMPLETED ══ -->
      {#if show("done") && done.length}
        <section class="group">
          <div class="group-head">
            <h2>Completed</h2>
            <span class="group-meta">{done.length} reports</span>
          </div>
          <div class="cards">
            {#each done as j (j.id)}
              <a class="job job-done" href="/design-preview/job">
                <div class="job-top">
                  <div class="job-id">
                    <span class="dot" style:background="var(--color-success-text)"></span>
                    <div>
                      <h3 class="job-title">{j.solutionName}</h3>
                      <p class="job-sub">{j.tagline}</p>
                    </div>
                  </div>
                  <span class="vbadge" style:color={verdictColor(j.verdict ?? "")}>{j.verdict}</span>
                </div>
                <div class="done-foot">
                  <span class="dfo">
                    <span class="dfo-item">D <b style:color={scoreColor(j.demand ?? 0)}>{j.demand}</b></span>
                    <span class="dfo-item">F <b style:color={scoreColor(j.feasibility ?? 0)}>{j.feasibility}</b></span>
                    <span class="dfo-item">O <b style:color={scoreColor(j.opportunity ?? 0)}>{j.opportunity}</b></span>
                    <span class="dfo-from">from {j.niche}</span>
                  </span>
                  <span class="done-open">{j.created} · Open report <ArrowRight size={13} aria-hidden="true" /></span>
                </div>
              </a>
            {/each}
          </div>
        </section>
      {/if}

      <!-- ══ ARCHIVED ══ -->
      {#if show("archived") && archived.length}
        <section class="group">
          <button class="group-head group-toggle" type="button" onclick={() => (archivedOpen = !archivedOpen)} aria-expanded={archivedShown}>
            <h2>Archived</h2>
            <span class="group-meta">{archived.length} cancelled or gated <ChevronDown size={15} class={archivedShown ? "chev chev-open" : "chev"} aria-hidden="true" /></span>
          </button>
          {#if archivedShown}
            <div class="cards">
              {#each archived as j (j.id)}
                <article class="job job-archived" style:--rail={STATUS[j.status].color}>
                  <div class="job-top">
                    <div class="job-id">
                      <span class="dot" style:background={STATUS[j.status].color}></span>
                      <div>
                        <h3 class="job-title">{j.niche}</h3>
                        <p class="job-meta">{j.entryMode} · {j.created}{#if j.creditRefunded} · credit refunded{/if}</p>
                      </div>
                    </div>
                    <span class="badge" style:color={STATUS[j.status].color}>{j.qualityGate ? "Quality gate" : STATUS[j.status].label}</span>
                  </div>
                  {#if j.qualityGate && j.error}<p class="arch-note">{j.error}</p>{/if}
                  <a class="link-action" href={rerunHref(j.niche)}>{j.qualityGate ? "Try a broader niche" : "Run again"} <ArrowRight size={13} aria-hidden="true" /></a>
                </article>
              {/each}
            </div>
          {/if}
        </section>
      {/if}

      {#if filter !== "all" && (buckets.find((b) => b.key === filter)?.count ?? 0) === 0}
        <p class="filter-empty">Nothing in this group right now.</p>
      {/if}
    {:else}
      <!-- ══ SAVED IDEAS TAB ══ -->
      <section class="group">
        <div class="group-head">
          <h2>Saved ideas</h2>
          <span class="group-meta">{savedIdeas.length} kept</span>
        </div>
        <div class="saved-grid">
          {#each savedIdeas as s (s.id)}
            <article class="saved">
              <div class="saved-top">
                <div>
                  <h3 class="saved-name">{s.name}</h3>
                  <p class="saved-tag">{s.tagline}</p>
                </div>
                <span class="saved-score" style:color={scoreColor(s.score)}>{s.score}</span>
              </div>
              <p class="saved-niche">{s.niche} · saved {s.added}</p>
              {#if s.note}
                <div class="saved-note">
                  <span class="note-label">Note</span>
                  <p>{s.note}</p>
                </div>
              {/if}
              <div class="saved-foot">
                <span class="vbadge" style:color={verdictColor(s.verdict)}>{s.verdict}</span>
                <a class="link-action" href="/design-preview/job">Open <ArrowRight size={13} aria-hidden="true" /></a>
              </div>
            </article>
          {/each}
        </div>
      </section>

      <section class="group">
        <div class="group-head">
          <h2>Saved pain points</h2>
          <span class="group-meta">{savedPains.length} kept · <span class="remix-hint">select 2+ to remix into new research</span></span>
        </div>
        <div class="pain-list">
          {#each savedPains as p (p.id)}
            <div class="pain-row">
              <span class="pain-sev" style:color={scoreColor(p.severity)} style:background="color-mix(in srgb, {scoreColor(p.severity)} 11%, transparent)">{p.severity}</span>
              <div class="pain-body">
                <p class="pain-title">{p.title}</p>
                <p class="pain-meta">{p.niche} · commercial intent {p.commercialIntent} · {p.mentions} mentions</p>
              </div>
              <button class="pain-remove" type="button" aria-label="Remove"><X size={14} aria-hidden="true" /></button>
            </div>
          {/each}
        </div>
      </section>
    {/if}
  </main>
</div>

<style>
  .page { display: grid; grid-template-columns: 320px 1fr; min-height: 100dvh; background: var(--color-bg-base); font-family: var(--font-body); color: var(--color-text-secondary); }

  /* ── LEFT SIDEBAR (job-page shell parity) ── */
  .sidebar { display: flex; flex-direction: column; border-right: 1px solid var(--color-border); padding: var(--space-6) var(--space-5) var(--space-5); position: sticky; top: 0; height: 100dvh; overflow-y: auto; }
  .proto { font-family: var(--font-mono); font-size: 0.625rem; letter-spacing: 0.03em; color: var(--color-text-muted); margin: 0 0 var(--space-5); }
  .proto a { color: var(--color-accent-hover); }
  .eyebrow { display: block; font-family: var(--font-mono); font-size: 0.6875rem; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600; color: var(--color-text-muted); }

  .side-nav { display: flex; flex-direction: column; gap: 0.15rem; margin: var(--space-4) 0 var(--space-6); }
  .side-tab { width: 100%; display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); background: transparent; border: 1px solid transparent; border-radius: var(--radius-lg); padding: var(--space-2) var(--space-3); font-family: var(--font-body); font-size: 0.9375rem; font-weight: 600; color: var(--color-text-muted); cursor: pointer; transition: background 0.15s ease, border-color 0.15s ease; }
  .side-tab:hover { background: var(--color-bg-surface); color: var(--color-text-secondary); }
  .side-tab:active { transform: scale(0.99); }
  .side-tab:focus-visible { outline: 2px solid var(--color-accent); outline-offset: -2px; }
  .side-tab-on { background: var(--color-accent-subtle); border-color: var(--color-border-accent); color: var(--color-text-primary); }
  .side-tab-on:hover { background: var(--color-accent-subtle); }
  .side-tab-count { font-family: var(--font-mono); font-size: 0.75rem; font-weight: 700; color: var(--color-text-muted); font-variant-numeric: tabular-nums; }
  .side-tab-on .side-tab-count { color: var(--color-accent-hover); }

  .side-label { display: block; font-family: var(--font-mono); font-size: 0.625rem; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600; color: var(--color-text-muted); margin-bottom: var(--space-3); padding: 0 var(--space-3); }

  .side-cta { margin-top: auto; padding-top: var(--space-6); }
  .btn-new { display: flex; align-items: center; justify-content: center; gap: 0.4rem; padding: var(--space-3) var(--space-4); border-radius: var(--radius-md); background: var(--color-accent); color: var(--color-white); font-size: 0.875rem; font-weight: 700; white-space: nowrap; transition: background 0.15s ease, transform 0.1s ease; }
  .btn-new:hover { background: var(--color-accent-hover); }
  .btn-new:active { transform: scale(0.98); }
  .btn-new:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  .side-credits { margin: var(--space-2) 0 0; font-family: var(--font-mono); font-size: 0.6875rem; color: var(--color-text-muted); text-align: center; }

  /* ── MAIN ── */
  .main { padding: var(--space-8) clamp(var(--space-6), 4vw, var(--space-10)) var(--space-16); max-width: 1180px; min-width: 0; }
  .main-head { margin-bottom: var(--space-8); }
  .main-head h1 { margin: 0; font-size: clamp(1.6rem, 3vw, 2.25rem); font-weight: 700; letter-spacing: -0.02em; line-height: 1.1; color: var(--color-text-primary); }
  .sub { margin: var(--space-3) 0 0; font-size: 0.9375rem; color: var(--color-text-muted); max-width: 70ch; }
  .s-hot { color: var(--color-accent-hover); font-weight: 700; }
  .s-dim { color: var(--color-text-muted); font-variant-numeric: tabular-nums; }

  /* groups */
  .group { margin-bottom: var(--space-8); }
  .group-head { display: flex; align-items: baseline; justify-content: space-between; gap: var(--space-4); margin-bottom: var(--space-4); width: 100%; }
  .group-head h2 { margin: 0; font-size: 1rem; font-weight: 700; color: var(--color-text-primary); }
  .group-meta { font-family: var(--font-mono); font-size: 0.6875rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-text-muted); display: inline-flex; align-items: center; gap: 0.4rem; }
  .remix-hint { text-transform: none; letter-spacing: 0; color: var(--color-accent-hover); }
  .group-toggle { background: none; border: none; cursor: pointer; text-align: left; padding: 0; }
  .group-toggle:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 3px; border-radius: var(--radius-sm); }
  .group-toggle :global(.chev) { transition: transform 0.15s ease; }
  .group-toggle :global(.chev-open) { transform: rotate(180deg); }

  .cards { display: flex; flex-direction: column; gap: var(--space-3); }

  /* job card */
  .job { display: block; position: relative; background: var(--color-bg-elevated); border: 1px solid var(--color-border); border-radius: var(--radius-xl); padding: var(--space-4) var(--space-5); }
  .job-attention { padding: var(--space-5); border-color: color-mix(in srgb, var(--rail) 35%, var(--color-border)); background: color-mix(in srgb, var(--rail) 7%, var(--color-bg-elevated)); }
  .job-archived { opacity: 0.85; }
  .job-top { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); }
  .job-id { display: flex; align-items: flex-start; gap: var(--space-3); min-width: 0; }
  .dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; margin-top: 0.4rem; }
  .dot-pulse { box-shadow: 0 0 0 0 color-mix(in srgb, var(--rail) 50%, transparent); animation: pulse 2s infinite; }
  @keyframes pulse { 0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--rail) 45%, transparent); } 70% { box-shadow: 0 0 0 6px transparent; } 100% { box-shadow: 0 0 0 0 transparent; } }
  .job-title { margin: 0; font-size: 0.9375rem; font-weight: 600; color: var(--color-text-primary); line-height: 1.3; }
  .job-meta { margin: 0.2rem 0 0; font-family: var(--font-mono); font-size: 0.6875rem; color: var(--color-text-muted); }
  .badge { flex-shrink: 0; display: inline-flex; align-items: center; font-size: 0.6875rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; padding: 0.2rem 0.5rem; border-radius: var(--radius-md); border: 1px solid color-mix(in srgb, currentColor 40%, transparent); background: var(--color-bg-elevated); }

  /* attention body */
  .action-body { margin-top: var(--space-4); display: flex; align-items: center; justify-content: space-between; gap: var(--space-4); flex-wrap: wrap; }
  .action-line { margin: 0; font-size: 0.875rem; color: var(--color-text-secondary); }
  .action-line strong { color: var(--color-text-primary); }
  .err { margin: 0; font-size: 0.875rem; line-height: 1.5; color: var(--color-text-secondary); max-width: 60ch; }
  .err-actions { display: inline-flex; align-items: center; gap: var(--space-4); flex-shrink: 0; }
  .refund { display: inline-flex; align-items: center; gap: 0.3rem; font-size: 0.75rem; color: var(--color-success-text); white-space: nowrap; }
  .btn-primary { display: inline-flex; align-items: center; gap: 0.4rem; padding: 0.5rem 0.9rem; border-radius: var(--radius-md); background: var(--color-accent); color: var(--color-white); font-size: 0.8125rem; font-weight: 700; white-space: nowrap; transition: background 0.15s ease, transform 0.1s ease; }
  .btn-primary:hover { background: var(--color-accent-hover); }
  .btn-primary:active { transform: scale(0.98); }

  /* progress */
  .prog { margin-top: var(--space-4); }
  .prog-bar { height: 5px; border-radius: 3px; background: var(--color-bg-surface); overflow: hidden; }
  .prog-bar span { display: block; height: 100%; border-radius: 3px; transition: width 0.4s ease; }
  .prog-meta { display: flex; align-items: center; justify-content: space-between; margin-top: 0.5rem; font-size: 0.8125rem; color: var(--color-text-secondary); }
  .prog-count { font-family: var(--font-mono); font-size: 0.6875rem; color: var(--color-text-muted); }
  .spin { margin: var(--space-4) 0 0; display: inline-flex; align-items: center; gap: 0.45rem; font-size: 0.8125rem; color: var(--color-text-secondary); }
  .spin :global(.spinner) { color: var(--color-warning-text); animation: spin 1s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .queue { margin: var(--space-3) 0 0; font-family: var(--font-mono); font-size: 0.75rem; color: var(--color-text-muted); }

  /* completed cards */
  .job-done { transition: background 0.15s ease, border-color 0.15s ease; }
  .job-done:hover { background: var(--color-bg-surface); border-color: var(--color-border-emphasis); }
  .job-done:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  .job-sub { margin: 0.2rem 0 0; font-size: 0.8125rem; color: var(--color-text-muted); line-height: 1.35; }
  .done-foot { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3) var(--space-4); margin-top: var(--space-3); padding-left: calc(8px + var(--space-3)); flex-wrap: wrap; }
  .dfo { display: inline-flex; align-items: center; gap: var(--space-4); font-family: var(--font-mono); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--color-text-muted); }
  .dfo-item b { font-weight: 700; font-size: 0.8125rem; font-variant-numeric: tabular-nums; }
  .dfo-from { text-transform: none; letter-spacing: 0; color: var(--color-text-muted); padding-left: var(--space-3); border-left: 1px solid var(--color-border); }
  .done-open { display: inline-flex; align-items: center; gap: 0.3rem; font-family: var(--font-mono); font-size: 0.75rem; color: var(--color-text-secondary); white-space: nowrap; }
  .job-done:hover .done-open { color: var(--color-text-primary); }
  .vbadge { display: inline-flex; flex-shrink: 0; font-size: 0.6875rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; padding: 0.15rem 0.45rem; border-radius: var(--radius-md); border: 1px solid color-mix(in srgb, currentColor 40%, transparent); }

  /* archived */
  .arch-note { margin: var(--space-3) 0 0; font-size: 0.8125rem; line-height: 1.5; color: var(--color-text-muted); }
  .link-action { display: inline-flex; align-items: center; gap: 0.3rem; margin-top: var(--space-3); font-family: var(--font-mono); font-size: 0.75rem; color: var(--color-text-secondary); }
  .link-action:hover { color: var(--color-text-primary); }

  /* saved ideas */
  .saved-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--space-4); }
  .saved { display: flex; flex-direction: column; background: var(--color-bg-elevated); border: 1px solid var(--color-border); border-radius: var(--radius-xl); padding: var(--space-5); }
  .saved-top { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3); }
  .saved-name { margin: 0; font-size: 1rem; font-weight: 700; color: var(--color-text-primary); }
  .saved-tag { margin: 0.25rem 0 0; font-size: 0.8125rem; line-height: 1.4; color: var(--color-text-secondary); }
  .saved-score { font-family: var(--font-mono); font-size: 1.25rem; font-weight: 700; flex-shrink: 0; font-variant-numeric: tabular-nums; }
  .saved-niche { margin: var(--space-3) 0 0; font-family: var(--font-mono); font-size: 0.6875rem; color: var(--color-text-muted); }
  .saved-note { margin: var(--space-3) 0 0; padding-left: var(--space-3); border-left: 2px solid var(--color-border-accent); }
  .note-label { display: block; font-family: var(--font-mono); font-size: 0.5625rem; text-transform: uppercase; letter-spacing: 0.07em; font-weight: 600; color: var(--color-accent-hover); margin-bottom: 0.25rem; }
  .saved-note p { margin: 0; font-size: 0.8125rem; font-style: italic; line-height: 1.5; color: var(--color-text-secondary); }
  .saved-foot { display: flex; align-items: center; justify-content: space-between; margin-top: auto; padding-top: var(--space-4); }

  /* saved pains */
  .pain-list { display: flex; flex-direction: column; }
  .pain-row { display: flex; align-items: center; gap: var(--space-4); padding: var(--space-3) 0; border-bottom: 1px solid var(--color-border); }
  .pain-row:last-child { border-bottom: none; }
  .pain-sev { flex-shrink: 0; width: 2.2rem; text-align: center; font-family: var(--font-mono); font-size: 0.8125rem; font-weight: 700; padding: 0.2rem 0; border-radius: var(--radius-md); }
  .pain-body { min-width: 0; flex: 1; }
  .pain-title { margin: 0; font-size: 0.875rem; font-weight: 600; color: var(--color-text-primary); line-height: 1.35; }
  .pain-meta { margin: 0.2rem 0 0; font-family: var(--font-mono); font-size: 0.6875rem; color: var(--color-text-muted); }
  .pain-remove { flex-shrink: 0; width: 26px; height: 26px; display: grid; place-items: center; border-radius: 50%; border: none; background: none; color: var(--color-text-muted); cursor: pointer; }
  .pain-remove:hover { background: var(--color-bg-hover); color: var(--color-text-primary); }

  /* filter rail (design-system .rail/.row idiom) */
  .filter-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0.15rem; }
  .filter-row { width: 100%; display: flex; align-items: center; gap: var(--space-3); background: transparent; border: 1px solid transparent; border-radius: var(--radius-lg); padding: var(--space-2) var(--space-3); cursor: pointer; text-align: left; transition: background 0.15s ease, border-color 0.15s ease; }
  .filter-row:hover { background: var(--color-bg-surface); }
  .filter-row:active { transform: scale(0.99); }
  .filter-row:focus-visible { outline: 2px solid var(--color-accent); outline-offset: -2px; }
  .filter-on { background: var(--color-accent-subtle); border-color: var(--color-border-accent); }
  .filter-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
  .filter-label { flex: 1; font-size: 0.875rem; font-weight: 500; color: var(--color-text-secondary); }
  .filter-on .filter-label { color: var(--color-text-primary); font-weight: 600; }
  .filter-count { font-family: var(--font-mono); font-size: 0.75rem; font-weight: 700; color: var(--color-text-muted); font-variant-numeric: tabular-nums; }
  .filter-on .filter-count { color: var(--color-accent-hover); }
  .filter-empty { font-size: 0.875rem; color: var(--color-text-muted); padding: var(--space-6) 0; text-align: center; }

  @media (max-width: 900px) {
    .page { grid-template-columns: 1fr; }
    .sidebar { position: static; height: auto; border-right: none; border-bottom: 1px solid var(--color-border); padding: var(--space-5) var(--space-5) var(--space-4); }
    .side-nav { flex-direction: row; margin: var(--space-4) 0; }
    .side-tab { width: auto; }
    .side-label { display: none; }
    .filter-list { flex-direction: row; overflow-x: auto; gap: var(--space-2); padding-bottom: var(--space-2); }
    .filter-row { width: auto; white-space: nowrap; border-color: var(--color-border); background: var(--color-bg-elevated); }
    .side-cta { display: flex; align-items: center; gap: var(--space-4); margin-top: var(--space-4); padding-top: 0; }
    .btn-new { width: auto; }
    .side-credits { margin: 0; }
    .main { padding: var(--space-6) var(--space-5) var(--space-12); max-width: none; }
  }
  @media (max-width: 820px) {
    .saved-grid { grid-template-columns: 1fr; }
  }
  @media (max-width: 560px) {
    .side-cta { flex-direction: column; align-items: stretch; }
    .btn-new { width: 100%; }
    .action-body, .err-actions { flex-direction: column; align-items: stretch; }
  }
  @media (prefers-reduced-motion: reduce) {
    * { transition: none !important; animation: none !important; }
  }
</style>
