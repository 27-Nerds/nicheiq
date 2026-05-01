<script lang="ts">
  import { mapVerdict, type Verdict } from "$lib/types/publicCatalog.js";

  // Renders the GO / CONDITIONAL / NO-GO chip with appropriate tone.
  // Accepts either a backend verdict ('GO' | 'NO_GO' | 'MAYBE') or a UI
  // verdict ('GO' | 'CONDITIONAL' | 'NO-GO'); mapVerdict normalises.

  interface Props {
    verdict: string | Verdict | null | undefined;
    /** Show the leading dot in the chip (default true). */
    dot?: boolean;
  }

  let { verdict, dot = true }: Props = $props();

  const ui = $derived(mapVerdict(verdict));
  const tone = $derived(
    ui === "GO" ? "success" : ui === "CONDITIONAL" ? "warn" : ui === "NO-GO" ? "error" : "muted",
  );
</script>

{#if ui}
  <span class="verdict-badge tone-{tone}">
    {#if dot}<span class="dot"></span>{/if}
    {ui}
  </span>
{/if}

<style>
  .verdict-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 2px 7px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.04em;
    border: 1px solid var(--color-border);
    background: var(--color-surface, #fff);
  }
  .dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: currentColor;
  }
  .tone-success {
    color: var(--color-success);
    border-color: rgba(34, 197, 94, 0.25);
    background: rgba(34, 197, 94, 0.04);
  }
  .tone-warn {
    color: var(--color-warning, #ca8a04);
    border-color: rgba(202, 138, 4, 0.25);
    background: rgba(202, 138, 4, 0.04);
  }
  .tone-error {
    color: var(--color-error, #dc2626);
    border-color: rgba(220, 38, 38, 0.25);
    background: rgba(220, 38, 38, 0.04);
  }
  .tone-muted {
    color: var(--color-text-muted);
  }
</style>
