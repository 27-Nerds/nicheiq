<script lang="ts">
  // Focused, full-screen "research in progress" view shown while a job generates
  // (Phase 1 Discovery + Phase 2 Deep Research). The job page hides its own chrome
  // (PhaseNav sidebar, hero, stepper, preview sections, meta footer) during
  // generation, so this screen OWNS the niche title + progress. Niche-led
  // hierarchy keeps it from reading as a generic loading splash; restrained
  // editorial styling (Plus Jakarta + JetBrains mono, hairline borders, no
  // shadows/animation/decoration) matches DocketEmpty / JobHeroAside.
  import Button from "$lib/components/ui/Button.svelte";
  import Breadcrumb from "$lib/components/ui/Breadcrumb.svelte";
  import SelectedSolutionsSummary from "$lib/components/SelectedSolutionsSummary.svelte";
  import { LayoutDashboard, Library, ArrowRight } from "lucide-svelte";
  import { IDEAS_HUB_PATH, painPointPath } from "$lib/utils/urls";
  import { scaleSeverity, type CatalogTopPainPoint } from "$lib/types/publicCatalog";
  import { IDEA_ICON, PAIN_ICON } from "$lib/config/entity-icons";
  import { getAdjustedStageCounts } from "$lib/utils/stages";
  import type { SolutionPreview } from "$lib/types/job";

  interface Props {
    phase: "discovery" | "deep_research";
    jobStatus: string;
    /** The guided-research route already owns the breadcrumb and niche title. */
    embedded?: boolean;
    niche?: string;
    entryMode?: string | null;
    userEmail?: string | null;
    progressPercent?: number;
    stagesCompleted?: number;
    totalStages?: number;
    currentStage?: number;
    currentStageName?: string | null;
    queuePosition?: number;
    catalogPainPoints?: CatalogTopPainPoint[];
    selectedNames?: string[];
    solutionIdeas?: SolutionPreview[];
    primaryWinner?: string | null;
    onCancel?: () => void;
    cancelling?: boolean;
  }

  let {
    phase,
    jobStatus,
    embedded = false,
    niche = "",
    entryMode = null,
    userEmail = null,
    progressPercent = 0,
    stagesCompleted = 0,
    totalStages = 0,
    currentStage = 0,
    currentStageName = null,
    queuePosition,
    catalogPainPoints = [],
    selectedNames = [],
    solutionIdeas = [],
    primaryWinner = null,
    onCancel,
    cancelling = false,
  }: Props = $props();

  const isDiscovery = $derived(phase === "discovery");
  const isQueued = $derived(jobStatus === "QUEUED" || jobStatus === "PENDING");

  const kicker = $derived(
    isQueued ? "Queued" : isDiscovery ? "Research in progress" : "Deep research",
  );

  // Catalog provenance caption (reuses the shared entity icons; self-hides otherwise).
  const provenance = $derived.by(() => {
    switch (entryMode) {
      case "deep_idea":
        return { Icon: IDEA_ICON, text: "Seeded from a catalog idea" };
      case "pain_research":
        return { Icon: PAIN_ICON, text: "Seeded from a catalog pain point" };
      case "pain_remix":
        return { Icon: PAIN_ICON, text: "Seeded from catalog pain points" };
      default:
        return null;
    }
  });

  const pct = $derived(Math.round(progressPercent ?? 0));

  // Same hidden-stage adjustment as the dashboard JobCard, so both surfaces
  // show identical "Stage N / M" numbers for the same job.
  const stageCounts = $derived(
    getAdjustedStageCounts({ stagesCompleted, totalStages, currentStage, status: jobStatus }),
  );
  const liveTitle = $derived(
    isQueued ? "Waiting for a worker" : currentStageName || "Research worker active",
  );
  const liveDetail = $derived(
    isQueued
      ? queuePosition
        ? `Queue position ${queuePosition}`
        : "The run is queued and will start automatically."
      : `Stage ${stageCounts.completed} of ${stageCounts.total}`,
  );

  // 3-phase pipeline track (replaces the hidden PhaseNav journey cue + the ring):
  // each segment renders done / active / queued / pending, with a fill bar.
  const phases = ["Discovery", "Deep Research", "Build"];
  const activePhase = $derived(isDiscovery ? 0 : 1);
  const phaseState = (i: number): "done" | "active" | "queued" | "pending" =>
    i < activePhase
      ? "done"
      : i === activePhase
        ? isQueued
          ? "queued"
          : "active"
        : "pending";
  const phaseFill = (i: number): number =>
    i < activePhase ? 100 : i === activePhase && !isQueued ? Math.max(pct, 4) : 0;

  // Precompute scaled severity so the template doesn't call scaleSeverity twice.
  const painRows = $derived(
    catalogPainPoints.map((pp) => ({ pp, sev: scaleSeverity(pp.severityScore, "pain") })),
  );
</script>

<div class="research-progress" class:research-progress--embedded={embedded}>
  {#if !embedded}
    <Breadcrumb items={[{ label: "Dashboard", href: "/dashboard" }]} current="Research" />
  {/if}

  <section class="rp-hero">
    <p class="rp-kicker">{kicker}</p>

    {#if niche && !embedded}
      <h1 class="rp-niche">{niche}</h1>
    {/if}

    {#if provenance}
      {@const Icon = provenance.Icon}
      <p class="rp-provenance">
        <Icon size={14} aria-hidden="true" />
        <span>{provenance.text}</span>
      </p>
    {/if}

    <div class="rp-live" role="status" aria-live="polite">
      <span class="rp-live-mark" data-state={isQueued ? "queued" : "running"} aria-hidden="true"></span>
      <span class="rp-live-copy">
        <strong>{liveTitle}</strong>
        <span>{liveDetail}</span>
      </span>
      <span class="rp-live-value">{isQueued ? "Queued" : `${pct}%`}</span>
    </div>

    <div class="rp-track" role="group" aria-label="Research progress">
      {#each phases as label, i}
        <div class="rp-seg" data-state={phaseState(i)}>
          <div class="rp-seg-meta">
            <span class="rp-seg-idx">{String(i + 1).padStart(2, "0")}</span>
            <span class="rp-seg-label">{label}</span>
          </div>
          <div class="rp-seg-bar">
            <div class="rp-seg-fill" style="width:{phaseFill(i)}%"></div>
          </div>
        </div>
      {/each}
    </div>

    <p class="rp-stage">
      {#if isQueued}
        In&nbsp;queue{#if queuePosition}&nbsp;· position {queuePosition}{/if}
      {:else}
        Stage {stageCounts.completed} / {stageCounts.total} · {pct}%
      {/if}
    </p>

    <p class="rp-body">
      {#if isDiscovery}
        This usually takes up to 15 minutes. You can safely close this tab — we'll email
        you{#if userEmail}&nbsp;at <strong>{userEmail}</strong>{/if} the moment it's ready.
      {:else}
        We're validating your top picks — the full market validation runs now. You can
        safely close this tab — we'll email you{#if userEmail}&nbsp;at <strong>{userEmail}</strong
        >{/if} when it's ready. <strong>Your discovery findings are saved</strong> and will be
        here with the full report.
      {/if}
    </p>

    <div class="rp-actions">
      <div class="rp-nav">
        <Button
          href="/dashboard"
          icon={LayoutDashboard}
          label="Return to Dashboard"
          class="btn-secondary"
        />
        <Button
          href={IDEAS_HUB_PATH}
          icon={Library}
          label="Browse Ideas Catalog"
          class="btn-secondary"
        />
      </div>
      {#if onCancel}
        <button type="button" class="rp-cancel" onclick={onCancel} disabled={cancelling}>
          {cancelling ? "Cancelling…" : "Cancel research"}
        </button>
      {/if}
    </div>
  </section>

  {#if !isDiscovery && selectedNames.length > 0}
    <section class="rp-selections">
      <SelectedSolutionsSummary {selectedNames} {solutionIdeas} {primaryWinner} status={jobStatus} />
    </section>
  {/if}

  {#if painRows.length > 0}
    <section class="rp-explore">
      <p class="rp-kicker">From the NicheIQ catalog</p>
      <h2 class="rp-explore-title">Validated problems from other research</h2>
      <ul class="rp-list">
        {#each painRows as { pp, sev } (pp.id)}
          <li>
            <a class="rp-row" href={painPointPath(pp.slug)}>
              <span class="rp-row-title">{pp.title}</span>
              <span class="rp-row-meta">
                {#if sev != null}SEV {sev} · {/if}{pp.mentionCount} mentions
                <ArrowRight class="rp-row-arrow" />
              </span>
            </a>
          </li>
        {/each}
      </ul>
    </section>
  {/if}
</div>

<style>
  .research-progress {
    max-width: 640px;
    margin: 0 auto;
  }
  .research-progress--embedded {
    max-width: none;
    margin: 0;
  }

  /* ── Hero zone — deliberate vertical presence, centered ── */
  /* Top-anchored (not vertically centered in a tall band) so the content sits
     just below the breadcrumb instead of floating mid-viewport. */
  .rp-hero {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    padding: 2rem 0 1.5rem;
  }
  .research-progress--embedded .rp-hero {
    position: relative;
    align-items: stretch;
    padding: clamp(1.25rem, 3vw, 2rem);
    overflow: hidden;
    text-align: left;
    background:
      radial-gradient(circle at 100% 0%, color-mix(in srgb, var(--color-accent) 8%, transparent), transparent 19rem),
      color-mix(in srgb, var(--color-bg-elevated) 96%, #f2e9dc);
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 52%, transparent);
    border-radius: var(--radius-xl);
    box-shadow: 0 1.25rem 3.5rem color-mix(in srgb, #6f5539 8%, transparent);
  }
  .research-progress--embedded .rp-hero::before {
    content: "";
    position: absolute;
    inset: 0 auto 0 0;
    width: 3px;
    background: var(--color-accent);
  }

  .rp-kicker {
    font-family: var(--font-mono);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
    color: var(--color-text-muted);
    margin: 0 0 0.75rem;
  }

  .rp-niche {
    font-family: var(--font-display);
    font-size: clamp(1.75rem, 4vw, 2.5rem);
    font-weight: 700;
    line-height: 1.12;
    letter-spacing: -0.02em;
    color: var(--color-text-primary);
    margin: 0 0 0.75rem;
    max-width: 24ch;
    text-wrap: balance;
  }

  /* ── Catalog provenance caption (entity icon + phrase) ── */
  .rp-provenance {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    margin: 0 0 1.25rem;
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.02em;
    color: var(--color-text-muted);
  }
  .rp-provenance :global(svg) {
    color: var(--color-accent);
    flex-shrink: 0;
  }

  /* Queue/execution truth from the job record, not an ambiguous spinner. */
  .rp-live {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    gap: 0.75rem;
    width: 100%;
    max-width: 480px;
    margin: 0 0 1.5rem;
    padding: 0.75rem 0.875rem;
    background: color-mix(in srgb, var(--color-bg-surface) 76%, transparent);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
  }
  .research-progress--embedded .rp-live {
    max-width: none;
  }
  .rp-live-mark {
    position: relative;
    width: 0.625rem;
    height: 0.625rem;
    border-radius: 50%;
    background: var(--color-accent);
  }
  .rp-live-mark::after {
    content: "";
    position: absolute;
    inset: -0.3rem;
    border: 1px solid color-mix(in srgb, var(--color-accent) 40%, transparent);
    border-radius: inherit;
    animation: rp-live-pulse 1.8s ease-out infinite;
  }
  .rp-live-mark[data-state="queued"] {
    background: var(--color-text-muted);
  }
  .rp-live-mark[data-state="queued"]::after {
    border-color: color-mix(in srgb, var(--color-text-muted) 38%, transparent);
    animation-duration: 2.8s;
  }
  @keyframes rp-live-pulse {
    0% { opacity: 0.9; transform: scale(0.65); }
    75%, 100% { opacity: 0; transform: scale(1.35); }
  }
  .rp-live-copy {
    display: grid;
    gap: 0.1rem;
    min-width: 0;
  }
  .rp-live-copy strong {
    overflow: hidden;
    font-family: var(--font-display);
    font-size: 0.875rem;
    font-weight: 650;
    color: var(--color-text-primary);
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .rp-live-copy span {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }
  .rp-live-value {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    color: var(--color-accent-dark);
  }

  /* ── Pipeline track (Discovery / Deep Research / Build) ── */
  .rp-track {
    display: flex;
    align-items: stretch;
    gap: 0.75rem;
    width: 100%;
    max-width: 480px;
    margin: 0 0 1rem;
  }
  .research-progress--embedded .rp-track {
    max-width: none;
  }
  .rp-seg {
    flex: 1 1 0;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    text-align: left;
  }
  .rp-seg-meta {
    display: flex;
    align-items: baseline;
    gap: 0.35rem;
    font-family: var(--font-mono);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    white-space: nowrap;
  }
  .rp-seg-idx {
    font-size: 9px;
    font-weight: 600;
    color: var(--color-text-muted);
    opacity: 0.6;
  }
  .rp-seg-label {
    font-size: 10px;
    font-weight: 600;
    color: var(--color-text-muted);
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .rp-seg-bar {
    position: relative;
    height: 3px;
    border-radius: 2px;
    background: var(--color-border);
    overflow: hidden;
  }
  .rp-seg-fill {
    position: absolute;
    inset: 0 auto 0 0;
    height: 100%;
    border-radius: 2px;
    background: var(--color-accent);
    transition: width 600ms cubic-bezier(0.4, 0, 0.2, 1);
  }
  /* state coloring */
  .rp-seg[data-state="done"] .rp-seg-label {
    color: var(--color-text-secondary);
  }
  .rp-seg[data-state="active"] .rp-seg-label,
  .rp-seg[data-state="active"] .rp-seg-idx {
    color: var(--color-accent);
    opacity: 1;
  }
  .rp-seg[data-state="queued"] .rp-seg-label {
    color: var(--color-text-secondary);
  }
  /* active = directional sweep over the fill → reads as "working / progressing" */
  .rp-seg[data-state="active"] .rp-seg-bar::after {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(
      90deg,
      transparent,
      color-mix(in srgb, var(--color-accent) 50%, transparent),
      transparent
    );
    transform: translateX(-100%);
    animation: rp-sweep 1.8s ease-in-out infinite;
  }
  @keyframes rp-sweep {
    to {
      transform: translateX(100%);
    }
  }
  /* queued = a gentle, non-directional idle pulse → reads as "waiting", not running */
  .rp-seg[data-state="queued"] .rp-seg-bar::after {
    content: "";
    position: absolute;
    inset: 0;
    background: color-mix(in srgb, var(--color-accent) 22%, transparent);
    animation: rp-pulse 2.4s ease-in-out infinite;
  }
  @keyframes rp-pulse {
    0%,
    100% {
      opacity: 0.3;
    }
    50% {
      opacity: 0.85;
    }
  }

  .rp-stage {
    font-family: var(--font-mono);
    font-size: 0.8125rem;
    font-variant-numeric: tabular-nums;
    letter-spacing: 0.02em;
    color: var(--color-text-secondary);
    margin: 0 0 1.75rem;
  }

  /* ── Orchestrated load reveal (one staggered cascade) ── */
  .rp-hero > * {
    animation: rp-rise 0.5s cubic-bezier(0.2, 0.7, 0.2, 1) both;
  }
  .rp-hero > *:nth-child(1) {
    animation-delay: 0.04s;
  }
  .rp-hero > *:nth-child(2) {
    animation-delay: 0.1s;
  }
  .rp-hero > *:nth-child(3) {
    animation-delay: 0.16s;
  }
  .rp-hero > *:nth-child(4) {
    animation-delay: 0.22s;
  }
  .rp-hero > *:nth-child(5) {
    animation-delay: 0.28s;
  }
  .rp-hero > *:nth-child(6) {
    animation-delay: 0.34s;
  }
  /* 7th child exists when the provenance caption renders (seeded jobs) —
     without this the actions block gets 0 delay and pops in first. */
  .rp-hero > *:nth-child(7) {
    animation-delay: 0.4s;
  }
  @keyframes rp-rise {
    from {
      opacity: 0;
      transform: translateY(6px);
    }
    to {
      opacity: 1;
      transform: none;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .rp-seg-fill {
      transition: none;
    }
    .rp-seg-bar::after {
      animation: none;
    }
    .rp-hero > * {
      animation: none;
    }
    .rp-live-mark::after {
      animation: none;
    }
  }

  /* ── Reassurance ── */
  .rp-body {
    font-size: 0.9375rem;
    line-height: 1.65;
    color: var(--color-text-secondary);
    max-width: 52ch;
    margin: 0 0 1.5rem;
  }
  .rp-body strong {
    color: var(--color-text-primary);
    font-weight: 600;
  }

  /* ── Actions — nav pair (centered row) + a set-apart cancel ── */
  .rp-actions {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1rem;
  }
  .research-progress--embedded .rp-actions {
    align-items: flex-start;
  }
  .rp-nav {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }
  .research-progress--embedded .rp-nav {
    justify-content: flex-start;
  }
  /* Lighter than the default btn-secondary for this calm waiting screen, and no
     hover lift (keep the accent border/colour hover). */
  .rp-nav :global(.btn-secondary) {
    padding: 0.625rem 1.125rem;
    font-size: var(--text-sm, 0.875rem);
  }
  .rp-nav :global(.btn-secondary:hover) {
    transform: none;
  }
  .rp-cancel {
    font-family: var(--font-body);
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--color-text-muted);
    background: transparent;
    border: 0;
    cursor: pointer;
    padding: 6px 10px;
    transition: color var(--duration-fast, 150ms) ease;
  }
  .rp-cancel:hover:not(:disabled) {
    color: var(--color-error, #ef4444);
  }
  .rp-cancel:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  /* ── Phase-2 selected solutions ── */
  .rp-selections {
    margin: 1rem 0 0;
  }

  /* ── Explore list — calm, static, editorial ── */
  .rp-explore {
    margin-top: 3rem;
    text-align: center;
  }
  .rp-explore-title {
    margin: 0 0 1rem;
    font-family: var(--font-display);
    font-size: 1.125rem;
    font-weight: 600;
    letter-spacing: -0.01em;
    color: var(--color-text-primary);
  }
  .rp-list {
    list-style: none;
    margin: 0;
    padding: 0;
    text-align: left;
    border-top: 1px solid var(--color-border);
  }
  .rp-row {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.875rem 0.5rem;
    border-bottom: 1px solid var(--color-border);
    text-decoration: none;
    transition: background-color var(--duration-fast, 150ms) ease;
  }
  .rp-row:hover {
    background: var(--color-bg-surface);
  }
  .rp-row-title {
    font-family: var(--font-display);
    font-size: 0.9375rem;
    font-weight: 500;
    line-height: 1.4;
    color: var(--color-text-primary);
  }
  .rp-row:hover .rp-row-title {
    color: var(--color-accent);
  }
  .rp-row-meta {
    flex-shrink: 0;
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    font-family: var(--font-mono);
    font-size: 0.75rem;
    font-variant-numeric: tabular-nums;
    color: var(--color-text-muted);
    white-space: nowrap;
  }
  .rp-row-meta :global(.rp-row-arrow) {
    width: 14px;
    height: 14px;
    color: var(--color-text-muted);
  }
  .rp-row:hover .rp-row-meta :global(.rp-row-arrow) {
    color: var(--color-accent);
  }

  @media (max-width: 480px) {
    .research-progress--embedded .rp-hero {
      padding: 1.125rem 1rem 1.25rem;
      border-radius: var(--radius-lg);
      box-shadow: none;
    }
    .rp-live {
      margin-bottom: 1.25rem;
    }
    .rp-seg-meta {
      align-items: flex-start;
      white-space: normal;
    }
    .rp-seg-label {
      line-height: 1.25;
    }
    .rp-nav {
      flex-direction: column;
      align-items: stretch;
      width: 100%;
    }
    .rp-row {
      flex-direction: column;
      align-items: flex-start;
      gap: 0.25rem;
    }
  }
</style>
