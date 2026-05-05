<script lang="ts">
  // Single source of truth for chip styling and tone variants across the
  // catalog. Hover is color-only by project convention — no transform lifts,
  // no accent border-bottom.

  interface Props {
    label: string;
    /** Visual emphasis. Default 'neutral' matches today's `.badge` look. */
    tone?: 'neutral' | 'accent' | 'info' | 'mono';
    /** Mono-font variant for source IDs / SKU-like values. Implies smaller text. */
    mono?: boolean;
  }

  let { label, tone = 'neutral', mono = false }: Props = $props();
</script>

<span class="chip tone-{tone}" class:mono>{label}</span>

<style>
  .chip {
    display: inline-flex;
    align-items: center;
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 500;
    border: 1px solid var(--color-border);
    color: var(--color-text-secondary, var(--color-text-primary));
    background: var(--color-surface, #fff);
    transition: background-color 120ms ease;
  }
  /* Color-only hover, per project memory feedback_no_ai_slop_hover. */
  .chip:hover {
    background: var(--color-surface-elevated, #fafafa);
  }
  .tone-accent {
    color: var(--color-accent, #b45309);
    border-color: var(--color-accent, #b45309);
    background: var(--color-surface, #fff);
  }
  .tone-info {
    color: var(--color-info);
    border-color: var(--color-info);
  }
  .tone-mono,
  .mono {
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.04em;
    text-transform: lowercase;
    font-weight: 500;
  }
</style>
