<script lang="ts">
  import type { PainPointPreview } from "$lib/types/catalog-landing.js";
  import { scaleSeverity } from "$lib/types/publicCatalog.js";
  import SeverityBar from "./SeverityBar.svelte";
  import { painPointPath } from "$lib/utils/urls";

  // # / title / mentions / severity table. Rows link to the pain detail page.

  interface Props {
    painPoints: PainPointPreview[];
  }

  let { painPoints }: Props = $props();
</script>

<div class="table">
  <div class="head row">
    <span class="num-h">#</span>
    <span>Pain point</span>
    <span class="right">Mentions</span>
    <span class="right">Severity</span>
  </div>
  {#each painPoints as p, i}
    <a class="row body" href={painPointPath(p.slug ?? "")}>
      <span class="num">{String(i + 1).padStart(2, "0")}</span>
      <span class="title">{p.title}</span>
      <span class="mentions">{(p.mentionCount ?? 0).toLocaleString()}</span>
      <span class="sev-cell">
        <SeverityBar value={scaleSeverity(p.severityScore, "pain")} />
      </span>
    </a>
  {/each}
</div>

<style>
  .table {
    /* width:100% is required because the wrapping `<a>` rows are inline by
       default and short content (rows have only a few words) lets the
       grid container shrink to its min-content width. Force full width
       so the table fills its parent's content box like the mockup. */
    width: 100%;
    border: 1px solid var(--color-border);
    border-radius: 8px;
    background: var(--color-surface, #fff);
    overflow: hidden;
  }
  .row {
    width: 100%;
    box-sizing: border-box;
  }
  .row {
    display: grid;
    grid-template-columns: 40px 1fr 110px 110px;
    gap: 14px;
    padding: 12px 16px;
    align-items: center;
    border-bottom: 1px solid var(--color-border);
  }
  .row:last-child {
    border-bottom: none;
  }
  .head {
    background: var(--color-surface-elevated, #fafafa);
    font-size: 10px;
    color: var(--color-text-muted);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    font-weight: 600;
    padding: 10px 16px;
  }
  .num-h {
    font-weight: 600;
  }
  .right {
    text-align: right;
  }
  .body {
    cursor: pointer;
    color: inherit;
    text-decoration: none;
    transition: background 0.12s;
  }
  .body:hover {
    background: var(--color-surface-elevated, #fafafa);
  }
  .body:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: -2px;
    background: var(--color-surface-elevated, #fafafa);
  }
  .num {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--color-text-muted);
    font-weight: 600;
  }
  .title {
    font-size: 13px;
    color: var(--color-text-primary);
    font-weight: 500;
  }
  .mentions {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--color-text-secondary, var(--color-text-primary));
    text-align: right;
  }
  /* Right-justify the severity bar + number so they hug the column's
     trailing edge together. Without this wrap, the SeverityBar's `inline-flex`
     stretches across the grid cell and the number drifts apart from the bar. */
  .sev-cell {
    display: flex;
    justify-content: flex-end;
  }
</style>
