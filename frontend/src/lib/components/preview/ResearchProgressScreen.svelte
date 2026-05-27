<script lang="ts">
  // Lean in-page "while you wait" panel shown during research generation
  // (Phase 1 Discovery + Phase 2 Deep Research). Deliberately NOT a hero: the
  // job page already renders the niche title, spinning status badge, progress
  // ring, Stage X/Y and Elapsed (PageHeader + JobHeroAside) above this block.
  // This panel only adds what those lack — the "you can leave, we'll email you"
  // reassurance, exit actions, and (Phase 1) a calm list of validated pain
  // points to explore. Frameless editorial styling mirrors DocketEmpty /
  // JobHeroAside; no shadows, no animation, no auto-scroll.
  import Button from "$lib/components/ui/Button.svelte";
  import SelectedSolutionsSummary from "$lib/components/SelectedSolutionsSummary.svelte";
  import { LayoutDashboard, Library, ArrowRight } from "lucide-svelte";
  import { IDEAS_HUB_PATH, painPointPath } from "$lib/utils/urls";
  import { scaleSeverity, type CatalogTopPainPoint } from "$lib/types/publicCatalog";
  import type { SolutionPreview } from "$lib/types/job";

  interface Props {
    phase: "discovery" | "deep_research";
    jobStatus: string;
    userEmail?: string | null;
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
    userEmail = null,
    catalogPainPoints = [],
    selectedNames = [],
    solutionIdeas = [],
    primaryWinner = null,
    onCancel,
    cancelling = false,
  }: Props = $props();

  const isDiscovery = $derived(phase === "discovery");
  const isQueued = $derived(jobStatus === "QUEUED" || jobStatus === "PENDING");

  const kicker = $derived(isDiscovery ? "While we work" : "Deep research");
  const headline = $derived(
    !isDiscovery
      ? "Validating your top picks."
      : isQueued
        ? "You're in the queue."
        : "Your research is underway.",
  );

  // Precompute the scaled severity so the template doesn't call scaleSeverity twice.
  const painRows = $derived(
    catalogPainPoints.map((pp) => ({ pp, sev: scaleSeverity(pp.severityScore, "pain") })),
  );
</script>

<div class="research-progress">
  {#if !isDiscovery && selectedNames.length > 0}
    <div class="rp-selections">
      <SelectedSolutionsSummary
        {selectedNames}
        {solutionIdeas}
        {primaryWinner}
        status={jobStatus}
      />
    </div>
  {/if}

  <section class="rp-reassure">
    <p class="rp-kicker">{kicker}</p>
    <h2 class="rp-headline">{headline}</h2>
    <p class="rp-body">
      {#if isDiscovery}
        {#if isQueued}
          You're next in line. We'll start the moment a slot opens and email you{#if userEmail}
            at <strong>{userEmail}</strong>{/if} when your report is ready.
        {:else}
          Discovery usually takes up to 15 minutes. We'll email you{#if userEmail}
            at <strong>{userEmail}</strong>{/if} the moment your report is ready — feel free
          to close this tab.
        {/if}
      {:else}
        Deep research runs the full market validation — competitors, demand, and positioning.
        We'll email you{#if userEmail} at <strong>{userEmail}</strong>{/if} when it's ready.
        Your discovery preview is below.
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

  {#if isDiscovery && painRows.length > 0}
    <section class="rp-explore">
      <p class="rp-kicker">While you wait · Validated pain points</p>
      <h2 class="rp-explore-title">Real problems founders are validating</h2>
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
    margin-top: 1.5rem;
  }

  .rp-selections {
    margin-bottom: 1.5rem;
  }

  /* ── Mono kicker — matches JobHeroAside .kicker ── */
  .rp-kicker {
    font-family: var(--font-mono);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
    color: var(--color-text-muted);
    margin: 0 0 8px;
  }

  /* ── Reassurance — frameless editorial, matches DocketEmpty ── */
  .rp-headline {
    margin: 0 0 0.625rem;
    font-family: var(--font-display);
    font-size: 1.375rem;
    font-weight: 600;
    line-height: 1.25;
    letter-spacing: -0.015em;
    color: var(--color-text-primary);
    max-width: 40ch;
  }

  .rp-body {
    margin: 0 0 1.5rem;
    font-size: 0.9375rem;
    line-height: 1.65;
    color: var(--color-text-secondary);
    max-width: 56ch;
  }
  .rp-body strong {
    color: var(--color-text-primary);
    font-weight: 600;
  }

  .rp-actions {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  /* Quiet, de-emphasized cancel — mono link, muted until hover. */
  .rp-cancel {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--color-accent);
    letter-spacing: 0.04em;
    text-decoration: none;
    border: 0;
    border-bottom: 1px solid currentColor;
    background: transparent;
    cursor: pointer;
    display: inline-block;
    padding: 8px 0 9px;
    margin: -8px 0 -9px;
  }
  .rp-cancel:hover:not(:disabled) {
    color: var(--color-accent-hover, var(--color-accent));
  }
  .rp-cancel:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 4px;
    border-radius: 2px;
  }
  .rp-cancel:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  /* ── Explore list — calm, static, editorial (no cards/gradients/scroll) ── */
  .rp-explore {
    margin-top: 2.5rem;
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
    }
    .rp-row {
      flex-direction: column;
      align-items: flex-start;
      gap: 0.25rem;
    }
  }
</style>
