<script lang="ts">
  import { ArrowRight, ChevronDown } from "lucide-svelte";
  import type { RuledOutFinding } from "$lib/types/report";

  interface Props {
    findings: RuledOutFinding[];
    highlightedIndex: number | null;
    onOpen: (finding: RuledOutFinding) => void;
  }

  let { findings, highlightedIndex, onOpen }: Props = $props();
  let expanded = $state(true);

  function bandLabel(band: string): string {
    return band === "very-low" ? "Very thin market" : "Thin market";
  }
</script>

<div class="ruled-out-panel" id="examined-ruled-out">
  <button
    type="button"
    class="ruled-out-head"
    aria-expanded={expanded}
    aria-controls="examined-ruled-out-list"
    onclick={() => (expanded = !expanded)}
  >
    <span class="ruled-out-head-copy">
      <span>Examined &amp; ruled out</span>
      <span class="ruled-out-head-description">
        Concepts tied to researched pains that did not clear the final market-fit checks. Review why they were excluded.
      </span>
    </span>
    <strong>{findings.length}</strong>
    <ChevronDown
      class={`ruled-out-chevron ${expanded ? "ruled-out-chevron--open" : ""}`}
      aria-hidden="true"
    />
  </button>
  <ul class="ruled-out-list" id="examined-ruled-out-list" role="list" hidden={!expanded}>
      {#each findings as finding, index}
        <li
          class="ruled-out-row"
          class:ruled-out-row--highlight={highlightedIndex === index}
          data-ruled-out-index={index}
        >
          <button
            type="button"
            class="ruled-out-row-button"
            onclick={() => onOpen(finding)}
          >
            <div class="ruled-out-main">
              <span class="sr-only">Review analysis for </span>
              <span class="ruled-out-pain">{finding.idea_name || finding.pain_title}</span>
              {#if finding.source_frame === "user_seed"}
                <span class="ruled-out-badge">Your idea</span>
              {/if}
              <span class="ruled-out-band">{bandLabel(finding.market_fit_band)}</span>
              <span class="ruled-out-view">View analysis <ArrowRight class="ruled-out-view-icon" aria-hidden="true" /></span>
            </div>
            {#if finding.idea_name && finding.idea_name !== finding.pain_title}
              <p class="ruled-out-provenance"><strong>Pain</strong> {finding.pain_title}</p>
            {/if}
            <p class="ruled-out-reason">{finding.reason}</p>
            {#if finding.evidence?.trim()}
              <p class="ruled-out-evidence">&ldquo;{finding.evidence}&rdquo;</p>
            {/if}
          </button>
        </li>
      {/each}
  </ul>
</div>

<style>
  .ruled-out-panel {
    display: grid;
    gap: 0;
    overflow: hidden;
    background: var(--color-bg-surface);
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 56%, transparent);
    border-radius: 0.5rem;
  }
  .ruled-out-head {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    width: 100%;
    padding: 0.4rem 0.7rem;
    border: 0;
    border-bottom: 1px solid color-mix(in srgb, var(--color-border-emphasis) 42%, transparent);
    appearance: none;
    background: color-mix(in srgb, var(--color-bg-surface) 74%, var(--color-bg-elevated));
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 800;
    letter-spacing: 0.08em;
    text-align: left;
    text-transform: uppercase;
    cursor: pointer;
    transition: background var(--duration-fast) var(--ease-default);
  }
  .ruled-out-head:hover {
    background: color-mix(in srgb, var(--color-accent) 4%, transparent);
  }
  .ruled-out-head:active {
    transform: scale(0.98);
  }
  .ruled-out-head:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .ruled-out-head-copy {
    display: grid;
    gap: 0.16rem;
  }
  .ruled-out-head-description {
    max-width: 68ch;
    color: var(--color-text-secondary);
    font-family: var(--font-body);
    font-size: 0.6875rem;
    font-weight: 400;
    line-height: 1.35;
    letter-spacing: normal;
    text-transform: none;
    text-wrap: pretty;
  }
  .ruled-out-head strong {
    display: grid;
    min-width: 1.1rem;
    height: 1.1rem;
    padding: 0 0.25rem;
    place-items: center;
    border-radius: 999px;
    background: var(--color-bg-elevated);
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
  }
  .ruled-out-head :global(svg) {
    width: 0.9rem;
    height: 0.9rem;
    margin-left: auto;
    transition: transform var(--duration-fast) var(--ease-default);
  }
  .ruled-out-head[aria-expanded="true"] :global(svg) { transform: rotate(180deg); }
  .ruled-out-list[hidden] { display: none; }
  .ruled-out-list {
    display: grid;
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .ruled-out-row {
    border-top: 1px solid var(--color-border);
    background: var(--color-bg-elevated);
  }
  .ruled-out-row:first-child { border-top: 0; }
  .ruled-out-row-button {
    display: grid;
    gap: 0.2rem;
    width: 100%;
    padding: 0.62rem 0.7rem;
    border: 0;
    background: transparent;
    color: inherit;
    text-align: left;
    cursor: pointer;
    transition: background var(--duration-fast) var(--ease-default);
  }
  .ruled-out-row-button:hover {
    background: color-mix(in srgb, var(--color-accent) 4%, transparent);
  }
  .ruled-out-row-button:active {
    background: color-mix(in srgb, var(--color-accent) 8%, transparent);
  }
  .ruled-out-row-button:focus-visible {
    position: relative;
    outline: 2px solid var(--color-accent);
    outline-offset: -2px;
  }
  .ruled-out-row--highlight { animation: ruled-out-flash 2.4s ease-out; }
  .ruled-out-main {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 0.5rem;
  }
  .ruled-out-pain {
    color: var(--color-text-primary);
    font-family: var(--font-body);
    font-size: 0.8125rem;
    font-weight: 700;
  }
  .ruled-out-view {
    display: inline-flex;
    align-items: center;
    gap: 0.2rem;
    margin-left: auto;
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }
  .ruled-out-view :global(svg) { width: 0.75rem; height: 0.75rem; }
  .ruled-out-badge {
    display: inline-flex;
    align-items: center;
    padding: 0.06rem 0.36rem;
    border: 1px solid color-mix(in srgb, var(--color-accent) 40%, transparent);
    border-radius: 0.375rem;
    background: color-mix(in srgb, var(--color-accent) 10%, transparent);
    color: var(--color-accent-dark);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 800;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    white-space: nowrap;
  }
  .ruled-out-provenance {
    margin: 0;
    color: var(--color-text-muted);
    font-size: 0.75rem;
  }
  .ruled-out-provenance strong {
    margin-right: 0.3rem;
    color: var(--color-text-secondary);
    font-weight: 700;
  }
  .ruled-out-band {
    display: inline-flex;
    align-items: center;
    padding: 0.06rem 0.36rem;
    border: 1px solid var(--color-border);
    border-radius: 0.375rem;
    background: var(--color-bg-surface);
    color: var(--color-text-secondary);
    font-family: var(--font-body);
    font-size: 0.625rem;
    font-weight: 700;
    white-space: nowrap;
  }
  .ruled-out-reason {
    max-width: 78ch;
    margin: 0;
    color: var(--color-text-secondary);
    font-size: 0.75rem;
    line-height: 1.42;
    text-wrap: pretty;
  }
  .ruled-out-evidence {
    max-width: 74ch;
    margin: 0.1rem 0 0;
    padding-left: 0.6rem;
    border-left: 1px solid var(--color-border-emphasis);
    color: var(--color-text-muted);
    font-size: 0.75rem;
    font-style: italic;
    line-height: 1.4;
  }
  @keyframes ruled-out-flash {
    0%, 30% { background: color-mix(in srgb, var(--color-accent) 16%, var(--color-bg-elevated)); }
    100% { background: var(--color-bg-elevated); }
  }
  @media (prefers-reduced-motion: reduce) {
    .ruled-out-row--highlight {
      animation: none;
      outline: 2px solid var(--color-accent);
      outline-offset: -2px;
    }
    .ruled-out-head:active {
      transform: none;
    }
  }
</style>
