<script lang="ts">
  // Focused, full-screen "research in progress" view shown while a job generates
  // (Phase 1 Discovery + Phase 2 Deep Research). The job page hides its own chrome
  // (PhaseNav sidebar, hero, stepper, preview sections, meta footer) during
  // generation, so this screen OWNS the niche title + progress. Niche-led
  // hierarchy keeps it from reading as a generic loading splash; restrained
  // editorial styling (Plus Jakarta + JetBrains mono, hairline borders, no
  // shadows/animation/decoration) matches DocketEmpty / JobHeroAside.
  import Button from "$lib/components/ui/Button.svelte";
  import SelectedSolutionsSummary from "$lib/components/SelectedSolutionsSummary.svelte";
  import ProgressRing from "$lib/components/ui/ProgressRing.svelte";
  import { LayoutDashboard, Library, ArrowRight } from "lucide-svelte";
  import { IDEAS_HUB_PATH, painPointPath } from "$lib/utils/urls";
  import { scaleSeverity, type CatalogTopPainPoint } from "$lib/types/publicCatalog";
  import type { SolutionPreview } from "$lib/types/job";

  interface Props {
    phase: "discovery" | "deep_research";
    jobStatus: string;
    niche?: string;
    userEmail?: string | null;
    progressPercent?: number;
    stagesCompleted?: number;
    totalStages?: number;
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
    niche = "",
    userEmail = null,
    progressPercent = 0,
    stagesCompleted = 0,
    totalStages = 0,
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

  const ringValue = $derived(Math.min(Math.max((progressPercent ?? 0) / 100, 0), 1));
  const pct = $derived(Math.round(progressPercent ?? 0));

  // Static 3-phase orientation breadcrumb (replaces the hidden PhaseNav journey cue).
  const phases = ["Discovery", "Deep Research", "Build"];
  const activePhase = $derived(isDiscovery ? 0 : 1);

  // Precompute scaled severity so the template doesn't call scaleSeverity twice.
  const painRows = $derived(
    catalogPainPoints.map((pp) => ({ pp, sev: scaleSeverity(pp.severityScore, "pain") })),
  );
</script>

<div class="research-progress">
  <section class="rp-hero">
    <p class="rp-kicker">{kicker}</p>

    {#if niche}
      <h1 class="rp-niche">{niche}</h1>
    {/if}

    <nav class="rp-phases" aria-label="Research phases">
      {#each phases as label, i}
        {#if i > 0}<span class="rp-phase-sep" aria-hidden="true">·</span>{/if}
        <span class="rp-phase" class:active={i === activePhase}>{label}</span>
      {/each}
    </nav>

    <div class="rp-progress">
      {#if isQueued}
        <p class="rp-stage">Queued{#if queuePosition} · position {queuePosition}{/if}</p>
      {:else}
        <ProgressRing
          value={ringValue}
          color="accent"
          size={72}
          showValue={false}
          showTooltip={false}
          flat
          glow={false}
          label="Research progress"
          class="rp-ring"
        />
        <p class="rp-stage">Stage {stagesCompleted} / {totalStages} · {pct}%</p>
      {/if}
    </div>

    <p class="rp-body">
      {#if isDiscovery}
        This usually takes up to 15 minutes. You can safely close this tab — we'll email
        you{#if userEmail} at <strong>{userEmail}</strong>{/if} the moment it's ready.
      {:else}
        We're validating your top picks — the full market validation runs now. You can
        safely close this tab — we'll email you{#if userEmail} at <strong>{userEmail}</strong
        >{/if} when it's ready. <strong>Your discovery findings are saved</strong> and will be
        here with the full report.
      {/if}
    </p>

    <div class="rp-actions">
      <Button
        href="/dashboard"
        icon={LayoutDashboard}
        label="Return to Dashboard"
        class="btn-primary"
      />
      <Button
        href={IDEAS_HUB_PATH}
        icon={Library}
        label="Browse Ideas Catalog"
        class="btn-secondary"
      />
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

  /* ── Hero zone — deliberate vertical presence, centered ── */
  .rp-hero {
    min-height: 55vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 2.5rem 0 1.5rem;
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
    margin: 0 0 1rem;
    max-width: 24ch;
    text-wrap: balance;
  }

  /* ── Phase breadcrumb (static orientation) ── */
  .rp-phases {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    margin: 0 0 1.75rem;
  }
  .rp-phase.active {
    color: var(--color-accent);
    font-weight: 600;
  }
  .rp-phase-sep {
    opacity: 0.5;
  }

  /* ── Progress ── */
  .rp-progress {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 1.75rem;
  }
  /* The ring is a status indicator here, not the interactive score widget —
     override ProgressRing's `cursor: help` (its `flat` variant doesn't reset it). */
  .rp-progress :global(.progress-ring.rp-ring) {
    cursor: default;
  }
  .rp-stage {
    font-family: var(--font-mono);
    font-size: 0.8125rem;
    font-variant-numeric: tabular-nums;
    letter-spacing: 0.02em;
    color: var(--color-text-secondary);
    margin: 0;
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

  /* ── Actions ── */
  .rp-actions {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }
  .rp-cancel {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    font-weight: 500;
    letter-spacing: 0.04em;
    color: var(--color-text-muted);
    background: transparent;
    border: 0;
    border-bottom: 1px solid transparent;
    cursor: pointer;
    padding: 8px 2px;
  }
  .rp-cancel:hover:not(:disabled) {
    color: var(--color-error, #ef4444);
    border-bottom-color: currentColor;
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
    .rp-actions {
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
