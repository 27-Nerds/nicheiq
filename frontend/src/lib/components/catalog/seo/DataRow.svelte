<script lang="ts">
  import type { Snippet } from 'svelte';

  // One row in a <DataList>. Renders the canonical dashed-border metadata
  // row used across catalog consumer pages: mono accent-muted uppercase
  // kicker on the left, primary-color value on the right.

  interface Props {
    /** Kicker text on the left column. */
    label: string;
    /** Stack the label above the value instead of side-by-side grid.
     *  Use for wide-value content (e.g. multi-line prose) or for
     *  vertical-stack contexts like CategoryHeroAside. */
    stack?: boolean;
    /** Cross-axis alignment of label and value cells. Default 'baseline'
     *  is right for text-with-text rows; use 'center' for rows whose
     *  value contains a visualization (bar, progress, icon) where the
     *  text baseline reads off relative to the graphic. */
    align?: 'baseline' | 'center';
    children: Snippet;
  }

  let { label, stack = false, align = 'baseline', children }: Props = $props();
</script>

<div class="data-row" class:stack class:align-center={align === 'center'}>
  <span class="data-row-label">{label}</span>
  <div class="data-row-value">{@render children()}</div>
</div>

<style>
  .data-row {
    display: grid;
    grid-template-columns: 110px 1fr;
    gap: 10px;
    align-items: baseline;
    padding: 10px 0;
    border-bottom: 1px dashed var(--color-border);
  }
  .data-row.stack {
    grid-template-columns: 1fr;
    gap: 4px;
    padding: 12px 0;
    align-items: start;
  }
  .data-row.align-center {
    align-items: center;
  }
  .data-row-label {
    font-family: var(--font-mono);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
    color: var(--color-accent-muted);
  }
  .data-row-value {
    font-size: 13px;
    line-height: 1.5;
    color: var(--color-text-primary);
  }

  /* Mobile: collapse side-by-side grid to stacked so a fixed 110px label
     column doesn't crush the value column on narrow viewports. */
  @media (max-width: 480px) {
    .data-row:not(.stack) {
      grid-template-columns: 1fr;
      gap: 4px;
    }
  }
</style>
