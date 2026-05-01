<script lang="ts">
  // Single-line sub-niche cell. Matches the mockup `.cat-sub` shape:
  // compact `Name … <count>` with the count right-aligned in mono.
  // Used inside CategoryAccordion bodies (index page) and SubNicheGrid
  // (category page) — both want the dense editorial treatment.

  interface Props {
    name: string;
    href: string;
    count?: number | null;
    /** Optional secondary line (e.g., "12 ideas") — when set, renders a
     *  taller two-line cell. Reserved for non-niche callers; default mode
     *  is the compact single-line treatment. */
    secondary?: string | null;
  }

  let { name, href, count = null, secondary = null }: Props = $props();
</script>

<a class="cell" class:two-line={secondary != null} {href}>
  <span class="name">{name}</span>
  {#if secondary}
    <span class="secondary">{secondary}</span>
  {:else if count != null}
    <span class="n">{count > 0 ? count.toLocaleString() : "—"}</span>
  {/if}
</a>

<style>
  /* Compact single-line treatment by default — name fills the row, count
     is monospaced and right-aligned. Two-line mode (secondary text) kept
     for callers that need it but isn't the catalog-rebuild default. */
  .cell {
    background: var(--color-surface, #fff);
    padding: 10px 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    cursor: pointer;
    transition: all 0.12s ease;
    color: inherit;
    text-decoration: none;
    font-size: 13px;
    min-height: 40px;
  }
  .cell.two-line {
    padding: 12px 16px;
    align-items: flex-start;
    flex-direction: column;
    gap: 2px;
  }
  .cell:hover {
    background: var(--color-surface-elevated, #fafafa);
  }
  .cell:hover .name {
    color: var(--color-accent);
  }
  .name {
    color: var(--color-text-secondary, var(--color-text-primary));
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    transition: color 0.12s ease;
  }
  .n {
    color: var(--color-text-muted);
    font-size: 11px;
    font-family: var(--font-mono);
    flex-shrink: 0;
    font-feature-settings: "tnum" 1;
  }
  .secondary {
    font-size: 11px;
    color: var(--color-text-muted);
  }

  @media (prefers-reduced-motion: reduce) {
    .cell,
    .name {
      transition: none;
    }
  }
</style>
