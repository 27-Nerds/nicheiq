<script lang="ts">
  import type { PainPointPreview } from "$lib/types/catalog-landing.js";
  import { scaleSeverity } from "$lib/types/publicCatalog.js";
  import SeverityBar from "./SeverityBar.svelte";
  import { painPointPath } from "$lib/utils/urls";

  // Right-rail aside on the category landing hero: top pain point + a 3-tile
  // mini-stat grid (top segment / top tool / top frustration term). Renders
  // nothing when no signals are available — the parent still renders the
  // hero, just without the aside slot.

  interface MiniStat {
    label: string;
    value: string | null;
  }

  interface Props {
    topPainPoint?: PainPointPreview | null;
    topSegment?: string | null;
    topTool?: string | null;
    topFrustrationTerm?: string | null;
  }

  let {
    topPainPoint = null,
    topSegment = null,
    topTool = null,
    topFrustrationTerm = null,
  }: Props = $props();

  const stats: MiniStat[] = $derived([
    { label: "Top segment", value: topSegment },
    { label: "Tool in use", value: topTool },
    { label: "Frustration", value: topFrustrationTerm },
  ]);

  const hasAny = $derived(
    !!topPainPoint || stats.some((s) => !!s.value),
  );
</script>

{#if hasAny}
  <aside class="cat-aside">
    {#if topPainPoint}
      <a class="top-pain" href={painPointPath(topPainPoint.slug ?? "")}>
        <span class="kicker">Top pain point</span>
        <span class="pain-title">{topPainPoint.title}</span>
        <SeverityBar value={scaleSeverity(topPainPoint.severityScore, "pain")} />
      </a>
    {/if}
    {#if stats.some((s) => !!s.value)}
      <div class="stat-grid">
        {#each stats as s}
          {#if s.value}
            <div class="stat">
              <div class="l">{s.label}</div>
              <div class="n">{s.value}</div>
            </div>
          {/if}
        {/each}
      </div>
    {/if}
  </aside>
{/if}

<style>
  .cat-aside {
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 20px 22px;
    border: 1px solid var(--color-border);
    border-radius: 8px;
    background: var(--color-surface-elevated, #fafafa);
  }
  .top-pain {
    display: flex;
    flex-direction: column;
    gap: 6px;
    color: inherit;
    text-decoration: none;
    padding: 4px 0;
    border-bottom: 1px solid var(--color-border);
    transition: opacity 0.12s;
  }
  .top-pain:hover {
    opacity: 0.85;
  }
  .top-pain:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 4px;
    border-radius: 4px;
  }
  .kicker {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--color-text-muted);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    font-weight: 600;
  }
  .pain-title {
    font-size: 14px;
    font-weight: 600;
    line-height: 1.35;
    color: var(--color-text-primary);
    letter-spacing: -0.005em;
  }
  .stat-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 10px;
    padding-top: 4px;
  }
  .stat {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .l {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--color-text-muted);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    font-weight: 600;
  }
  .n {
    font-size: 13px;
    font-weight: 500;
    color: var(--color-text-primary);
    line-height: 1.4;
  }
</style>
