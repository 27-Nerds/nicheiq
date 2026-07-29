<script lang="ts">
  import { ChevronDown } from "lucide-svelte";
  import type { Snippet } from "svelte";
  import { APPENDIX_EYEBROW } from "$lib/selection/labels";

  interface Props {
    /** ONE plain meta line ("3 analyst notes · 2 feedback notes · 4 ideas ruled out"). */
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
      <span class="appendix-title">How the shortlist was formed</span>
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
    padding: 0;
    overflow: hidden;
  }
  .appendix-trigger {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-4);
    width: 100%;
    padding: var(--space-4);
    border: 0;
    border-radius: var(--radius-xl);
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
    gap: var(--space-1);
    min-width: 0;
  }
  .appendix-eyebrow {
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }
  .appendix-title {
    color: var(--color-text-primary);
    font-family: var(--font-display);
    font-size: var(--text-md);
    font-weight: 700;
    line-height: var(--leading-tight);
  }
  .appendix-meta {
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-11);
    font-weight: 500;
    line-height: var(--leading-normal);
    font-variant-numeric: tabular-nums;
    font-feature-settings: "zero" 0;
  }
  .analysis-appendix :global(.appendix-chevron) {
    flex: 0 0 auto;
    width: var(--space-4);
    height: var(--space-4);
    color: var(--color-text-muted);
    transition: transform var(--duration-normal) var(--ease-default);
  }
  .analysis-appendix :global(.appendix-chevron--open) {
    transform: rotate(180deg);
  }
  .appendix-body[hidden] { display: none; }
  .appendix-body {
    display: grid;
    gap: var(--space-6);
    padding: var(--space-5) var(--space-4) var(--space-4);
    border-top: 1px solid var(--color-border);
  }
  .appendix-body :global(.context-notes) {
    padding-top: var(--space-4);
    border-top: 1px solid var(--color-border);
  }
  .appendix-body :global(.context-disclosures) {
    width: 100%;
    margin-left: 0;
    justify-content: flex-start;
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
