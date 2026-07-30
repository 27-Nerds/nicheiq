<script lang="ts">
  import { tourLauncher } from "./tourLauncher.svelte";

  /**
   * Manual re-entry into the current surface's chapter.
   *
   * Renders only while a `TourHost` is mounted, which means it is automatically absent
   * on surfaces with no chapter and for users without the decision-tools grant — no
   * separate gating needed here.
   */
</script>

{#if tourLauncher.available}
  <button
    type="button"
    class="tour-restart"
    onclick={() => tourLauncher.restart()}
  >
    Show me around again
  </button>
{/if}

<style>
  .tour-restart {
    font-family: var(--font-body);
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--color-text-secondary);
    background: transparent;
    border: 1px solid var(--color-border-emphasis);
    border-radius: var(--radius-md);
    padding: var(--space-1-5) var(--space-3);
    cursor: pointer;
    white-space: nowrap;
    transition: background-color 0.15s ease, color 0.15s ease;
  }

  .tour-restart:hover {
    background-color: var(--color-bg-subtle);
    color: var(--color-text-primary);
  }

  .tour-restart:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
</style>
