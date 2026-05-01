<script lang="ts">
  import type { Snippet } from "svelte";

  // Inline section header rendered as "01 · LABEL ────── right-slot".
  // Used to demarcate sections inside a long-form catalog page.

  interface Props {
    /** 1-based section number. Padded to 2 digits ("01"). Omit to hide. */
    num?: number | null;
    label: string;
    /** Right-slot snippet (e.g. count text, action button). */
    right?: Snippet;
  }

  let { num = null, label, right }: Props = $props();

  const formattedNum = $derived(
    num == null ? null : String(num).padStart(2, "0"),
  );
</script>

<div class="section-divider">
  <span class="lbl">
    {#if formattedNum}
      <span class="num">{formattedNum}</span>
      <span class="dot">·</span>
    {/if}
    {label}
  </span>
  <span class="line"></span>
  <span class="right">
    {@render right?.()}
  </span>
</div>

<style>
  .section-divider {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 40px 0 16px;
  }
  .lbl {
    font-size: 11px;
    color: var(--color-text-muted);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 600;
  }
  .num {
    color: var(--color-text-primary);
    font-weight: 700;
  }
  .dot {
    margin: 0 4px;
  }
  .line {
    flex: 1;
    height: 1px;
    background: var(--color-border);
  }
  .right :global(*) {
    font-size: 11px;
    color: var(--color-text-muted);
  }
</style>
