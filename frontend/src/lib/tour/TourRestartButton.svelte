<script lang="ts">
  import { tourLauncher } from "./tourLauncher.svelte";

  /**
   * Manual re-entry into the current surface's chapter.
   *
   * Renders only while a mounted `TourHost` has REGISTERED with the launcher, which it
   * does while it has a chapter, the decision-tools grant, and no suppression — so this
   * control is absent on surfaces with no chapter, for users without the grant, and on a
   * surface whose chapter has been withheld. No separate gating needed here.
   *
   * That last clause was false until 2026-08-14: the host registered unconditionally at
   * mount, so a "Show me around again" button sat on a `not_evaluated` idea check and
   * replayed the tour's "run it again in your own words" — the exact sentence the verdict
   * card had been fixed to stop saying. If a call site needs this control gone, the lever
   * is `TourHost`'s `suppressed`, never its `ready`.
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
