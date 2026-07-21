<script lang="ts">
  import { ChevronDown } from "lucide-svelte";
  import type { Snippet } from "svelte";
  import { APPENDIX_EYEBROW } from "$lib/selection/labels";

  interface Props {
    /** ONE plain mono meta line ("Analyst notes 3 · Collaborator 2 · Ruled out 4"). */
    meta: string;
    /** Collapsed by default; bindable so the workbench can force it open
     *  (e.g. when scrolling to a ruled-out entry inside). */
    expanded?: boolean;
    children: Snippet;
  }

  let { meta, expanded = $bindable(false), children }: Props = $props();
</script>

<!-- Dossier appendix (DESIGN_SYSTEM §5.5): wears the existing discovery-dossier
     chrome (global class — reused, not forked); trigger/meta are appendix-only. -->
<section class="discovery-dossier analysis-appendix" data-annotation-anchor="analysis-appendix">
  <button
    type="button"
    class="appendix-trigger"
    aria-expanded={expanded}
    aria-controls="analysis-appendix-body"
    onclick={() => (expanded = !expanded)}
  >
    <span class="appendix-id">
      <span class="appendix-eyebrow">{APPENDIX_EYEBROW}</span>
      {#if meta}
        <span class="appendix-meta">{meta}</span>
      {/if}
    </span>
    <ChevronDown class="appendix-chevron {expanded ? 'appendix-chevron--open' : ''}" aria-hidden="true" />
  </button>
  <div class="appendix-body" id="analysis-appendix-body" hidden={!expanded}>
    {@render children()}
  </div>
</section>

<style>
  .analysis-appendix {
    /* The dossier chrome supplies border/radius/background/shadow; the appendix
       tightens its inset so the trigger's own padding sets the 1rem frame. */
    padding: 0.25rem;
  }
  .appendix-trigger {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    width: 100%;
    padding: 0.75rem;
    border: 0;
    border-radius: calc(var(--radius-xl) - 0.25rem);
    background: transparent;
    font: inherit;
    text-align: left;
    cursor: pointer;
    transition: background var(--duration-fast, 150ms) var(--ease-default);
  }
  .appendix-trigger:hover {
    background: color-mix(in srgb, var(--color-bg-surface) 60%, transparent);
  }
  .appendix-trigger:active {
    transform: scale(0.98);
  }
  .appendix-trigger:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .appendix-id {
    display: grid;
    gap: 0.25rem;
    min-width: 0;
  }
  .appendix-eyebrow {
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 800;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }
  .appendix-meta {
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-11);
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    font-variant-numeric: tabular-nums;
    font-feature-settings: "zero" 0;
  }
  .analysis-appendix :global(.appendix-chevron) {
    flex: 0 0 auto;
    width: 1rem;
    height: 1rem;
    color: var(--color-text-muted);
    transition: transform 200ms cubic-bezier(0.32, 0.72, 0, 1);
  }
  .analysis-appendix :global(.appendix-chevron--open) {
    transform: rotate(180deg);
  }
  .appendix-body[hidden] { display: none; }
  .appendix-body {
    display: grid;
    gap: 0.75rem;
    padding: 0.25rem 0.75rem 0.75rem;
  }
  @media (prefers-reduced-motion: reduce) {
    .appendix-trigger,
    .analysis-appendix :global(.appendix-chevron) {
      transition: none;
    }
    .appendix-trigger:active {
      transform: none;
    }
  }
</style>
