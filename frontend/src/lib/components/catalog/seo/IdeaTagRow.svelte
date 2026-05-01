<script lang="ts">
  // Mono tag row "Category / Sub · Idea #ID" used in the idea/pain-point hero.

  interface Props {
    categoryName: string;
    /** Optional sub-category. */
    subName?: string | null;
    /** Optional accented suffix, e.g. "Idea #abc123". */
    suffix?: string | null;
  }

  let { categoryName, subName = null, suffix = null }: Props = $props();
</script>

<div class="tag-row">
  <span>{categoryName}</span>
  {#if subName}
    <span class="sep">/</span>
    <span>{subName}</span>
  {/if}
  {#if suffix}
    <span class="sep">·</span>
    <span class="accent">{suffix}</span>
  {/if}
</div>

<style>
  .tag-row {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--color-text-muted);
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .accent {
    color: var(--color-accent);
    font-weight: 600;
  }
  .sep {
    color: var(--color-text-muted);
    opacity: 0.6;
  }
</style>
