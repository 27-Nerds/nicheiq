<script lang="ts">
  // Focused, full-screen "research in progress" view shown while a job generates
  // (Phase 1 Discovery + Phase 2 Deep Research). The job page hides its own chrome
  // (PhaseNav sidebar, hero, stepper, preview sections, meta footer) during
  // generation, so this screen OWNS the niche title + progress. Niche-led
  // hierarchy keeps it from reading as a generic loading splash; restrained
  // editorial styling (product sans + mono tokens, hairline borders, no
  // shadows/animation/decoration) matches DocketEmpty / JobHeroAside.
  import Button from "$lib/components/ui/Button.svelte";
  import Breadcrumb from "$lib/components/ui/Breadcrumb.svelte";
  import ConfirmGate from "$lib/components/ui/ConfirmGate.svelte";
  import SelectedSolutionsSummary from "$lib/components/SelectedSolutionsSummary.svelte";
  import { LayoutDashboard, Library, ListChecks, ArrowRight } from "lucide-svelte";
  import { IDEAS_HUB_PATH, painPointPath } from "$lib/utils/urls";
  import { scaleSeverity, type CatalogTopPainPoint } from "$lib/types/publicCatalog";
  import { IDEA_ICON, PAIN_ICON } from "$lib/config/entity-icons";
  import { getVisibleStageProgress, VISIBLE_TOTAL_STAGES } from "$lib/utils/stages";
  import type { SelectionDraftItem, SolutionPreview } from "$lib/types/job";

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
    stageArtifact?: Record<string, unknown> | null;
    queuePosition?: number;
    catalogPainPoints?: CatalogTopPainPoint[];
    selectedNames?: string[];
    selectedItems?: SelectionDraftItem[];
    solutionIdeas?: SolutionPreview[];
    primaryWinner?: string | null;
    primaryWinnerRef?: Pick<SelectionDraftItem, "ideaId" | "ideaRevision"> | null;
    jobId?: string;
    onCancel?: () => void;
    cancelling?: boolean;
    cancelLabel?: string;
    cancelConfirmLabel?: string;
    cancelConsequence?: string;
    cancelError?: string;
    connectionState?: "live" | "reconnecting" | "paused";
    onRefresh?: () => void;
  }

  let {
    phase,
    jobStatus,
    embedded = false,
    niche = "",
    entryMode = null,
    userEmail = null,
    stagesCompleted = 0,
    totalStages = 0,
    currentStage = 0,
    currentStageName = null,
    stageArtifact = null,
    queuePosition,
    catalogPainPoints = [],
    selectedNames = [],
    selectedItems = [],
    solutionIdeas = [],
    primaryWinner = null,
    primaryWinnerRef = null,
    jobId,
    onCancel,
    cancelling = false,
    cancelLabel = "Cancel research",
    cancelConfirmLabel = "Stop this run",
    cancelConsequence = "RUN STOPS · ELIGIBLE CREDITS REFUNDED",
    cancelError = "",
    connectionState = "live",
    onRefresh,
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
      // "Check my idea": static copy by design — the derived market lives only in
      // checkpoint state (never on the Job row), so it appears in the report's
      // parsed-idea echo at completion, not here.
      case "validate_idea":
        return { Icon: IDEA_ICON, text: "Checking your idea against this market" };
      default:
        return null;
    }
  });
  const isIdeaCheck = $derived(entryMode === "validate_idea");

  const DISCOVERY_VISIBLE_STAGES = 4;
  const DEEP_RESEARCH_VISIBLE_STAGES = VISIBLE_TOTAL_STAGES - DISCOVERY_VISIBLE_STAGES;

  // Start from the shared end-to-end projection used by other progress surfaces;
  // this focused screen converts it to phase-local progress immediately below.
  const stageProgress = $derived(
    getVisibleStageProgress({
      stagesCompleted,
      totalStages,
      currentStage,
      currentStageName,
      status: jobStatus,
    }),
  );
  // This screen presents Research and Deep Research as separate phases, so its
  // count and percentage must be phase-local. The shared projection has 14
  // visible steps end to end: 4 in Research (stages 3 + 4 are one public step)
  // and 10 in Deep Research (the optional landing-page build is excluded).
  const phaseStageProgress = $derived.by(() => {
    const offset = isDiscovery ? 0 : DISCOVERY_VISIBLE_STAGES;
    const total = isDiscovery ? DISCOVERY_VISIBLE_STAGES : DEEP_RESEARCH_VISIBLE_STAGES;
    return {
      completed: Math.max(0, Math.min(total, stageProgress.completed - offset)),
      current: Math.max(1, Math.min(total, stageProgress.current - offset)),
      total,
      label: isDiscovery ? "Research" : "Deep Research",
    };
  });
  const phasePct = $derived.by(() => {
    if (isQueued) return 0;
    return Math.round((phaseStageProgress.completed / phaseStageProgress.total) * 100);
  });
  const stageSubprogress = $derived.by(() => {
    if (currentStage !== 5 || !stageProgress.currentName || !stageArtifact) return null;
    if (
      stageArtifact.type !== "stage_subprogress"
      || stageArtifact.stage !== 5
      || typeof stageArtifact.code !== "string"
      || typeof stageArtifact.label !== "string"
    ) return null;
    const label = stageArtifact.label.trim();
    return label.length > 0 && label.length <= 100 ? label : null;
  });
  const liveTitle = $derived(
    isQueued
      ? "Waiting for a worker"
      : stageSubprogress || stageProgress.currentName || "Research worker active",
  );
  const liveDetail = $derived(
    isQueued
      ? queuePosition
        ? `Queue position ${queuePosition}`
        : "The run is queued and will start automatically."
      : stageProgress.currentCallbackIsComplete || !stageProgress.currentName
        ? `${phaseStageProgress.label}: ${phaseStageProgress.completed} of ${phaseStageProgress.total} steps complete`
        : `${phaseStageProgress.label} step ${phaseStageProgress.current} of ${phaseStageProgress.total}`,
  );

  // Purchased lifecycle only. "Build" is an optional post-report deliverable, not
  // an automatic research phase; the required user choice belongs between the runs.
  // Idea-check runs end at the idea's verdict, not an idea-picking step — "Pick
  // ideas" mid-run would teach exactly the wrong expectation.
  const phases = $derived(
    isIdeaCheck
      ? ["Research", "Your verdict", "Deep Research"]
      : ["Discovery", "Pick ideas", "Deep Research"],
  );
  const activePhase = $derived(isDiscovery ? 0 : 2);
  const phaseState = (i: number): "done" | "active" | "queued" | "pending" =>
    i < activePhase
      ? "done"
      : i === activePhase
        ? isQueued
          ? "queued"
          : "active"
        : "pending";
  const phaseFill = (i: number): number =>
    i < activePhase ? 100 : i === activePhase && !isQueued ? Math.max(phasePct, 4) : 0;

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

    {#if isIdeaCheck}
      <!-- The control-group sentence — echoed at the report's alternatives disclosure,
           so the generated pool reads as method, never a bait-and-switch. -->
      <p class="rp-method">
        We research the market your idea lives in, write your pitch up as a complete
        product spec — name included — and score it beside the other approaches that
        same evidence supports.
      </p>
    {/if}

    <div class="rp-status-panel">
      <p class="sr-only" role="status" aria-live="polite">
        {isQueued ? `${liveTitle}. ${liveDetail}.` : `${liveDetail}. Current activity: ${liveTitle}.`}
      </p>
      <div class="rp-live">
        <span class="rp-live-mark" data-state={isQueued ? "queued" : "running"} aria-hidden="true"></span>
        <span class="rp-live-copy">
          {#if isQueued}
            <strong>{liveTitle}</strong>
            <span>{liveDetail}</span>
          {:else}
            <span class="rp-live-context">{liveDetail}</span>
            <strong>{liveTitle}</strong>
          {/if}
        </span>
        <span class="rp-live-value">{isQueued ? "Queued" : `${phasePct}%`}</span>
      </div>

      {#if connectionState !== "live"}
        <div class="rp-connection" role="status">
          <span>
            {connectionState === "reconnecting"
              ? "Reconnecting live updates…"
              : "Live updates paused. The research continues in the background."}
          </span>
          {#if connectionState === "paused" && onRefresh}
            <button type="button" onclick={onRefresh}>Refresh status</button>
          {/if}
        </div>
      {/if}

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
    </div>

    <!-- The stage line that used to sit here restated what `.rp-live` already shows
         12rem above it, in both states: `liveDetail` renders "Stage N of M" while
         running and "Queue position N" when queued, and `rp-live-value` carries the
         percent / "Queued". Two readings of the same thing under one progress bar. -->

    <p class="rp-body">
      {#if isDiscovery}
        This usually takes under an hour. You can safely close this tab — we'll email
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
        {#if isDiscovery}
          <Button
            href={IDEAS_HUB_PATH}
            icon={Library}
            label="Browse Ideas Catalog"
            class="btn-secondary"
          />
        {:else if jobId}
          <Button
            href={`/jobs/${jobId}/selection/compare`}
            icon={ListChecks}
            label="Review research scope"
            class="btn-secondary"
          />
        {/if}
      </div>
      {#if onCancel}
        <!-- Cancellation changes paid operation state, so it is always armed through the
             two-step ConfirmGate. The caller supplies the exact consequence for Discovery
             (terminal run) versus queued Deep Research (return to selection). -->
        <div class="rp-cancel-gate">
          <ConfirmGate
            label={cancelLabel}
            confirmLabel={cancelConfirmLabel}
            variant="free"
            consequence={cancelConsequence}
            busy={cancelling}
            loadingText="Cancelling…"
            onConfirm={onCancel}
          />
        </div>
      {/if}
      {#if !isDiscovery && !isQueued && !onCancel}
        <p class="rp-cancel-note">
          Research has started and can no longer be cancelled. System failures refund eligible credits automatically.
        </p>
      {/if}
      {#if cancelError}
        <p class="rp-cancel-error" role="alert">{cancelError}</p>
      {/if}
    </div>
  </section>

  {#if !isDiscovery && selectedNames.length > 0}
    <section class="rp-selections">
      <SelectedSolutionsSummary
        {selectedNames}
        {selectedItems}
        {solutionIdeas}
        {primaryWinner}
        {primaryWinnerRef}
        showIdentity={true}
        {jobId}
        status={jobStatus}
      />
    </section>
  {/if}

  {#if isDiscovery && painRows.length > 0}
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
    width: 100%;
    max-width: none;
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
    font-size: var(--text-xs);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
    color: var(--color-text-muted);
    margin: 0 0 0.75rem;
  }

  .rp-niche {
    font-family: var(--font-display);
    font-size: var(--text-4xl);
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
    gap: var(--space-1-5);
    margin: 0 0 1.25rem;
    font-family: var(--font-mono);
    font-size: var(--text-11);
    letter-spacing: 0.02em;
    color: var(--color-text-muted);
  }
  .rp-provenance :global(svg) {
    color: var(--color-accent);
    flex-shrink: 0;
  }

  .rp-method {
    max-width: 56ch;
    margin: -0.5rem 0 1.25rem;
    font-size: 0.8125rem;
    line-height: 1.5;
    color: var(--color-text-secondary);
    text-wrap: pretty;
  }

  .rp-status-panel {
    display: contents;
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
    padding: var(--space-3) var(--space-3);
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
  .rp-live-mark[data-state="queued"] {
    background: var(--color-text-muted);
  }
  .rp-live-copy {
    display: grid;
    gap: 0.1rem;
    min-width: 0;
  }
  .rp-live-copy strong {
    overflow: hidden;
    font-family: var(--font-display);
    font-size: var(--text-base);
    font-weight: 600;
    color: var(--color-text-primary);
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .rp-live-copy span {
    font-size: var(--text-11);
    color: var(--color-text-secondary);
  }
  .rp-live-copy .rp-live-context {
    font-family: var(--font-mono);
    font-size: var(--text-10);
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .rp-live-value {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    color: var(--color-accent-dark);
  }
  .rp-connection {
    display: flex;
    width: 100%;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    margin: calc(-1 * var(--space-3)) 0 var(--space-5);
    color: var(--color-warning-text);
    font-size: var(--text-sm);
  }
  .rp-connection button {
    min-height: var(--space-8);
    padding-inline: var(--space-3);
    border: 1px solid var(--color-border-emphasis);
    border-radius: var(--radius-md);
    background: var(--color-bg-elevated);
    color: var(--color-text-primary);
    font: inherit;
    font-weight: 700;
    cursor: pointer;
    transition:
      border-color var(--duration-fast) ease,
      color var(--duration-fast) ease,
      transform var(--duration-fast) ease;
  }
  .rp-connection button:hover {
    border-color: var(--color-border-accent);
    color: var(--color-accent-dark);
  }
  .rp-connection button:active {
    transform: translateY(1px);
  }
  .rp-connection button:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
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
    gap: var(--space-1-5);
    font-family: var(--font-mono);
    text-transform: uppercase;
    letter-spacing: 0.07em;
    white-space: nowrap;
  }
  .rp-seg-idx {
    font-size: var(--text-xs);
    font-weight: 600;
    color: var(--color-text-muted);
    opacity: 0.6;
  }
  .rp-seg-label {
    font-size: var(--text-xs);
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
    transition: width 240ms cubic-bezier(0.4, 0, 0.2, 1);
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

  /* `.rp-stage` removed with its markup — it duplicated `.rp-live`. The track keeps the
     bottom spacing the removed element used to provide. */
  .rp-track {
    margin-block-end: var(--space-6);
  }

  @media (prefers-reduced-motion: reduce) {
    .rp-seg-fill {
      transition: none;
    }
    .rp-seg-bar::after {
      animation: none;
    }
  }

  /* ── Reassurance ── */
  .rp-body {
    font-size: var(--text-base);
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
    padding: var(--space-2) var(--space-4);
    font-size: var(--text-sm);
  }
  .rp-nav :global(.btn-secondary:hover) {
    transform: none;
  }
  .rp-cancel-gate {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
  }
  .rp-cancel-error {
    max-width: 58ch;
    margin: var(--space-2) 0 0;
    color: var(--color-error-text);
    font-size: var(--text-sm);
    line-height: var(--leading-normal);
  }
  .rp-cancel-note {
    max-width: 58ch;
    margin: 0;
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: var(--leading-normal);
  }
  .research-progress--embedded .rp-cancel-gate {
    align-items: flex-start;
    justify-content: flex-start;
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
    font-size: var(--text-xl);
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
    padding: var(--space-3) var(--space-2);
    border-bottom: 1px solid var(--color-border);
    text-decoration: none;
    transition: background-color var(--duration-fast, 150ms) ease;
  }
  .rp-row:hover {
    background: var(--color-bg-surface);
  }
  .rp-row:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
    background: var(--color-bg-surface);
  }
  .rp-row-title {
    font-family: var(--font-display);
    font-size: var(--text-base);
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
    font-size: var(--text-sm);
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

  /* The standalone job page gives this component a 56rem canvas. On wide screens,
     use that room for an editorial lead + a compact live-status rail instead of
     nesting a 40rem page and 30rem progress blocks inside it. Embedded research
     owns a separate card treatment and intentionally keeps its existing layout. */
  @media (min-width: 840px) {
    .research-progress:not(.research-progress--embedded) .rp-hero {
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(20rem, 0.8fr);
      grid-template-areas:
        "kicker status"
        "title status"
        "provenance status"
        "method status"
        "body status"
        "actions status";
      column-gap: var(--space-12);
      align-items: start;
      padding: clamp(var(--space-10), 5vw, var(--space-16)) 0 var(--space-12);
      text-align: left;
    }
    .research-progress:not(.research-progress--embedded) .rp-kicker {
      grid-area: kicker;
      margin-bottom: var(--space-3);
    }
    .research-progress:not(.research-progress--embedded) .rp-niche {
      grid-area: title;
      max-width: 23ch;
      margin-bottom: var(--space-4);
      font-size: clamp(var(--text-4xl), 2.5vw, 2.25rem);
      line-height: 1.08;
      letter-spacing: var(--tracking-tight);
    }
    .research-progress:not(.research-progress--embedded) .rp-provenance {
      grid-area: provenance;
      justify-self: start;
      margin-bottom: var(--space-5);
    }
    .research-progress:not(.research-progress--embedded) .rp-method {
      grid-area: method;
      max-width: 58ch;
      margin: 0 0 var(--space-6);
      font-size: var(--text-base);
      line-height: var(--leading-relaxed);
    }
    .research-progress:not(.research-progress--embedded) .rp-status-panel {
      grid-area: status;
      display: flex;
      flex-direction: column;
      gap: var(--space-6);
      min-width: 0;
    }
    .research-progress:not(.research-progress--embedded) .rp-live {
      max-width: none;
      margin: 0;
      padding: var(--space-4);
      background: color-mix(in srgb, var(--color-bg-surface) 88%, transparent);
    }
    .research-progress:not(.research-progress--embedded) .rp-connection {
      margin: calc(-1 * var(--space-3)) 0 0;
    }
    .research-progress:not(.research-progress--embedded) .rp-track {
      flex-direction: column;
      gap: 0;
      max-width: none;
      margin: 0;
      padding-inline: var(--space-1);
    }
    .research-progress:not(.research-progress--embedded) .rp-seg {
      position: relative;
      display: grid;
      grid-template-columns: var(--space-4) minmax(0, 1fr);
      min-height: var(--space-12);
      gap: var(--space-3);
    }
    .research-progress:not(.research-progress--embedded) .rp-seg:last-child {
      min-height: auto;
    }
    .research-progress:not(.research-progress--embedded) .rp-seg::before {
      content: "";
      grid-column: 1;
      align-self: start;
      width: var(--space-2);
      height: var(--space-2);
      margin-top: 0.125rem;
      border: 1px solid var(--color-border-emphasis);
      border-radius: var(--radius-full);
      background: var(--color-bg-elevated);
    }
    .research-progress:not(.research-progress--embedded) .rp-seg:not(:last-child)::after {
      content: "";
      position: absolute;
      top: 0.875rem;
      bottom: 0.25rem;
      left: calc(var(--space-1) - 0.5px);
      width: 1px;
      background: color-mix(in srgb, var(--color-border-emphasis) 72%, transparent);
    }
    .research-progress:not(.research-progress--embedded) .rp-seg[data-state="active"]::before,
    .research-progress:not(.research-progress--embedded) .rp-seg[data-state="done"]::before {
      border-color: var(--color-accent);
      background: var(--color-accent);
    }
    .research-progress:not(.research-progress--embedded) .rp-seg[data-state="active"]::before {
      box-shadow: 0 0 0 4px color-mix(in srgb, var(--color-accent) 12%, transparent);
    }
    .research-progress:not(.research-progress--embedded) .rp-seg[data-state="done"]::after {
      background: color-mix(in srgb, var(--color-accent) 38%, var(--color-border));
    }
    .research-progress:not(.research-progress--embedded) .rp-seg-meta {
      grid-column: 2;
      align-self: start;
      min-width: 0;
    }
    .research-progress:not(.research-progress--embedded) .rp-seg-label {
      overflow: visible;
      text-overflow: clip;
    }
    .research-progress:not(.research-progress--embedded) .rp-seg-bar {
      display: none;
    }
    .research-progress:not(.research-progress--embedded) .rp-body {
      grid-area: body;
      max-width: 58ch;
      margin-bottom: var(--space-6);
      font-size: var(--text-md);
      text-wrap: pretty;
    }
    .research-progress:not(.research-progress--embedded) .rp-actions {
      grid-area: actions;
      align-items: flex-start;
      gap: var(--space-3);
    }
    .research-progress:not(.research-progress--embedded) .rp-nav {
      justify-content: flex-start;
      gap: var(--space-5);
    }
    .research-progress:not(.research-progress--embedded) .rp-nav :global(.btn-secondary) {
      min-height: var(--space-10);
      padding: var(--space-2) var(--space-1);
      border: 0;
      border-radius: var(--radius-sm);
      background: transparent;
      box-shadow: none;
      color: var(--color-text-secondary);
    }
    .research-progress:not(.research-progress--embedded) .rp-nav :global(.btn-secondary:hover) {
      background: transparent;
      color: var(--color-accent-dark);
    }
    .research-progress:not(.research-progress--embedded) .rp-cancel-gate {
      align-items: flex-start;
      justify-content: flex-start;
    }
    .research-progress:not(.research-progress--embedded) .rp-cancel-gate :global(.gate-trigger) {
      min-width: 0;
      min-height: var(--space-8);
      padding: 0 var(--space-1);
      border: 0;
      border-radius: var(--radius-sm);
      color: var(--color-text-muted);
      font-weight: 600;
      text-decoration: underline;
      text-decoration-color: color-mix(in srgb, currentColor 45%, transparent);
      text-underline-offset: 0.2em;
    }
    .research-progress:not(.research-progress--embedded) .rp-cancel-gate :global(.gate-trigger:hover:not(:disabled)) {
      color: var(--color-error-text);
      text-decoration-color: currentColor;
    }
  }

  @media (max-width: 480px) {
    .rp-niche {
      font-size: var(--text-2xl);
    }
    .research-progress--embedded .rp-hero {
      padding: var(--space-4) var(--space-4) var(--space-5);
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
