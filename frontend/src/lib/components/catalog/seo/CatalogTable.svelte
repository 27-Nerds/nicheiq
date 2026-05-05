<script lang="ts">
  import type { Snippet } from "svelte";

  // Shared chrome for catalog data tables (PainPointRankTable, IdeasListTable).
  // Provides:
  //   - Outer container: 1px border, 8px radius, surface bg, overflow clipped
  //   - Header bar (.ct-head): bg-base tint, mono uppercase styling cascaded
  //     via :global rules
  //   - Body rows (.ct-row): hairline dividers between, hover bg-base, no
  //     reserved tier rail unless [data-tier] is set
  //
  // Single default-snippet slot — consumer renders both head and rows
  // directly inside CatalogTable. Lets consumer-local CSS scope to .ct-head
  // and .ct-row naturally (those elements live in the consumer's component).
  // Each consumer sets its own grid-template-columns + gap.

  interface Props {
    children: Snippet;
  }

  let { children }: Props = $props();
</script>

<div class="catalog-table">
  {@render children()}
</div>

<style>
  .catalog-table {
    border: 1px solid var(--color-border);
    border-radius: 8px;
    background: var(--color-bg-elevated, #fff);
    overflow: hidden;
  }
  /* Header bar — consumer renders <div class="ct-head">…</div> directly. */
  .catalog-table :global(.ct-head) {
    display: grid;
    align-items: center;
    padding: 13px 20px;
    background: var(--color-bg-base, #fafafa);
    border-bottom: 1px solid var(--color-border);
    font-size: 10px;
    color: var(--color-text-muted);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 600;
  }
  /* Body row baseline — consumer adds its own grid-template-columns + gap. */
  .catalog-table :global(.ct-row) {
    display: grid;
    align-items: center;
    padding: 18px 20px;
    border-bottom: 1px solid var(--color-border);
    color: inherit;
    text-decoration: none;
    transition: background 0.12s;
    position: relative;
  }
  .catalog-table :global(.ct-row:last-child) {
    border-bottom: none;
  }
  .catalog-table :global(a.ct-row:hover),
  .catalog-table :global(div.ct-row:hover) {
    background: var(--color-bg-base, #fafafa);
  }
  .catalog-table :global(a.ct-row:focus-visible),
  .catalog-table :global(.ct-row:focus-within) {
    outline: 2px solid var(--color-accent);
    outline-offset: -2px;
    background: var(--color-bg-base, #fafafa);
  }
  /* Tier rail via absolute pseudo-element — only renders when [data-tier]
     is present so untiered tables (IdeasListTable) have no reserved space.
     Mock spec at ideas-v2/styles.css:200-220. */
  .catalog-table :global(.ct-row[data-tier])::before {
    content: "";
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 3px;
  }
  .catalog-table :global(.ct-row[data-tier="high"])::before {
    background: var(--color-error);
  }
  .catalog-table :global(.ct-row[data-tier="med"])::before {
    background: var(--color-accent);
  }
  .catalog-table :global(.ct-row[data-tier="low"])::before {
    background: var(--color-info);
  }
</style>
