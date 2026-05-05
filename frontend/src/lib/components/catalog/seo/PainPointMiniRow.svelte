<script lang="ts">
  import type { PainPointPreview } from "$lib/types/catalog-landing.js";
  import { scaleSeverity } from "$lib/types/publicCatalog.js";
  import SeverityBar from "./SeverityBar.svelte";
  import { painPointPath } from "$lib/utils/urls";

  // Single source of truth for the pain-point preview row.
  // Used by ThemeCard's "Top pain points" mini-list and DominantTheme's
  // mini-list. Renders a quiet anchor row with a tier-color left rail,
  // title, mention count, and a compact severity bar (no HIGH/MED/LOW
  // pill — aria-label on the bar still announces the tier name for SR).
  //
  // CALLER RESPONSIBILITY: when nesting inside a <ul>, wrap each row in
  // an <li> for valid list semantics:
  //
  //   <ul>
  //     {#each painPoints as pp (pp.id)}
  //       <li><PainPointMiniRow painPoint={pp} /></li>
  //     {/each}
  //   </ul>

  interface Props {
    painPoint: PainPointPreview;
  }

  let { painPoint }: Props = $props();

  const sev = $derived(scaleSeverity(painPoint.severityScore, "pain"));
  const tier = $derived<"high" | "med" | "low">(
    sev == null ? "low" : sev >= 75 ? "high" : sev >= 60 ? "med" : "low",
  );
</script>

<a class="ppmr" data-tier={tier} href={painPointPath(painPoint.slug ?? "")}>
  <span class="ppmr-title">{painPoint.title}</span>
  <span class="ppmr-meta">
    <span class="ppmr-mentions">{painPoint.mentionCount.toLocaleString()}</span>
    <span class="ppmr-bar"><SeverityBar value={sev} showTier={false} /></span>
  </span>
</a>

<style>
  .ppmr {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 12px;
    align-items: center;
    padding: 8px 12px;
    color: inherit;
    text-decoration: none;
    border-left: 2px solid transparent;
    transition: background 0.12s;
  }
  .ppmr[data-tier="high"] {
    border-left-color: var(--color-error);
  }
  .ppmr[data-tier="med"] {
    border-left-color: var(--color-accent);
  }
  .ppmr[data-tier="low"] {
    border-left-color: var(--color-info);
  }
  .ppmr:hover {
    background: var(--color-bg-base, #fafafa);
  }
  .ppmr:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: -2px;
    background: var(--color-bg-base, #fafafa);
  }
  .ppmr-title {
    font-size: 12.5px;
    font-weight: 500;
    color: var(--color-text-primary);
    line-height: 1.4;
    min-width: 0;
    overflow-wrap: anywhere;
  }
  .ppmr-meta {
    display: inline-flex;
    align-items: center;
    gap: 10px;
  }
  .ppmr-mentions {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--color-text-muted);
    min-width: 24px;
    text-align: right;
  }
  .ppmr-bar {
    display: inline-flex;
  }

  @media (max-width: 640px) {
    .ppmr-meta {
      gap: 6px;
    }
  }
</style>
