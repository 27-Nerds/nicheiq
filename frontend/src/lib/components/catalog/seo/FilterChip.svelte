<script lang="ts">
  // Toggleable filter chip with optional count badge. Used by
  // AllIdeasSection's sub-niche filter row.

  interface Props {
    label: string;
    count?: number | null;
    active?: boolean;
    onclick: () => void;
  }

  let { label, count = null, active = false, onclick }: Props = $props();
</script>

<button class="chip" class:active type="button" {onclick}>
  {label}
  {#if count != null}
    <span class="count">{count.toLocaleString()}</span>
  {/if}
</button>

<style>
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 5px 11px;
    border-radius: 6px;
    font-size: 12px;
    color: var(--color-text-secondary, var(--color-text-primary));
    font-weight: 500;
    border: 1px solid var(--color-border);
    background: var(--color-surface);
    cursor: pointer;
    transition: all 0.12s ease;
    font-family: inherit;
  }
  .chip:hover {
    border-color: var(--color-border-emphasis);
    color: var(--color-text-primary);
  }
  .chip.active {
    background: var(--color-text-primary);
    color: var(--color-surface);
    border-color: var(--color-text-primary);
  }
  .count {
    color: var(--color-text-muted);
    font-size: 11px;
    font-family: var(--font-mono);
  }
  .chip.active .count {
    color: rgba(255, 255, 255, 0.7);
  }
</style>
