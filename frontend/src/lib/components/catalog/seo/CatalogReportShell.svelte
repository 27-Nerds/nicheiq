<script lang="ts">
  import type { ComponentType, Snippet } from "svelte";
  import SectionNav from "$lib/components/ui/SectionNav.svelte";

  // The shell composes the catalog detail/landing pages with the same sticky
  // section nav (1280 px+ desktop sidebar, mobile bottom-pill) used at
  // /shared/[shareToken]. Sections passed in are the ones with backing data —
  // empty sections never render an entry, so the rail auto-adapts to sparse
  // reports.
  interface Section {
    id: string;
    label: string;
    icon?: ComponentType;
  }

  interface Props {
    sections: Section[];
    children: Snippet;
    /** Minimum sections required to render the rail (default 3). Single- or
     *  two-section pages don't earn a rail — the lonely Hash icon reads as
     *  a status indicator rather than navigation. */
    minSections?: number;
    /** 'detail' = use .report-content max-width + padding (default; for
     *  /idea/[slug] and /pain-point/[slug] which render full-bleed).
     *  'catalog' = drop .report-content; rely on outer (public)/ideas
     *  layout (`.ideas-shell`, 56rem cap) for max-width + padding so we
     *  don't get double-padding inside an already-padded shell. */
    variant?: "detail" | "catalog";
    /** Phase 5.3: when true, the rail renders with always-visible labels
     *  (no hover-reveal collapse). Category pages pass true to match the
     *  reference design's "On This Page" rail. */
    railExpanded?: boolean;
  }

  let {
    sections,
    children,
    minSections = 3,
    variant = "detail",
    railExpanded = false,
  }: Props = $props();

  const showRail = $derived(sections.length >= minSections);
</script>

<div class="report-layout">
  {#if showRail}
    <SectionNav {sections} expanded={railExpanded} />
  {/if}
  <main
    class="catalog-shell"
    class:report-content={variant === "detail"}
    class:report-content--with-sidebar={variant === "detail" && showRail}
  >
    {@render children()}
  </main>
</div>

<style>
  .catalog-shell {
    /* Reuse .report-content max-width: 1200px from app.css. The sidebar pad
       (.report-content--with-sidebar) only kicks in at >=1280 px. */
    display: flex;
    flex-direction: column;
    gap: var(--space-12);
  }

  @media (max-width: 768px) {
    .catalog-shell {
      gap: var(--space-8);
    }
  }

  /* Standard scroll-margin so anchor jumps clear the sticky page header. */
  :global(.catalog-shell .section-anchor) {
    scroll-margin-top: 4rem;
  }

  /* Hairline divider between sections in lieu of stacked card chrome.
     First child has no top hairline. */
  :global(.catalog-shell > .section-anchor + .section-anchor) {
    border-top: 1px solid var(--color-border);
    padding-top: var(--space-12);
  }

  /* ============================================================
     Variant: public — flatten the reused dashboard sections so
     they read as editorial rather than SaaS-dashboard-exposed.
     The same components render with full chrome at
     /shared/[shareToken] (untouched), and flatter inside the
     catalog shell.
     ============================================================ */

  /* Drop the card-fill background on Section wrappers; let the shell's
     hairline + 48 px gap supply the boundary instead. */
  :global(.catalog-shell .report-section) {
    background: transparent;
    box-shadow: none;
    padding-bottom: 0;
    border-bottom: none;
  }

  /* Strip nested card fills from inner cards in the reused sections so we
     don't end up with cards-on-cards. Keep hairline borders; drop fills. */
  :global(.catalog-shell .report-section .card),
  :global(.catalog-shell .report-section .stat-card),
  :global(.catalog-shell .report-section .metric-card) {
    background: transparent !important;
    box-shadow: none !important;
  }

  /* Suppress green-success / red-error / amber-warning chromatic indicators
     on reused sections. Quality signal lives in the typographic provenance
     row above, not in dashboard traffic-lights. */
  :global(.catalog-shell .report-section [class*="success"]),
  :global(.catalog-shell .report-section [class*="warning"]),
  :global(.catalog-shell .report-section [class*="error"]) {
    background-color: transparent !important;
  }

  /* Reading column constraint inside the wider canvas — prose blocks max
     65ch even when the shell is 1200 px. Card grids stay full-width. */
  :global(.catalog-shell .report-section p),
  :global(.catalog-shell .report-section .description) {
    max-width: 65ch;
    text-wrap: pretty;
  }
</style>
