<script lang="ts">
  /**
   * Informational coverage notes for an idea set: pain-concentration and
   * uncovered-pain signals (from the backend's quality_caveats). Read-only,
   * muted meta styling — never an alert, never orange. Renders nothing when empty.
   */
  interface Props {
    notes?: string[] | null;
    /** Tighter padding when shown inline above the ideas grid vs. as a report block. */
    compact?: boolean;
  }
  let { notes = [], compact = false }: Props = $props();

  const items = $derived(
    (notes ?? []).filter((n) => typeof n === "string" && n.trim().length > 0),
  );
</script>

{#if items.length}
  <section
    class="rounded-lg border border-border bg-bg-surface {compact ? 'p-3' : 'p-4'}"
    aria-label="Idea-set coverage notes"
  >
    <p class="text-[11px] font-mono uppercase tracking-wider text-text-muted">
      Coverage notes
    </p>
    <ul class="mt-2 space-y-1.5">
      {#each items as note}
        <li
          class="text-xs text-text-secondary leading-relaxed pl-3 border-l-2 border-border-emphasis"
        >
          {note}
        </li>
      {/each}
    </ul>
  </section>
{/if}
