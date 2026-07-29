<script lang="ts">
  import { ArrowRight } from "lucide-svelte";
  import type { RuledOutFinding } from "$lib/types/report";

  interface Props {
    findings: RuledOutFinding[];
    highlightedIndex: number | null;
    onOpen: (finding: RuledOutFinding) => void;
  }

  let { findings, highlightedIndex, onOpen }: Props = $props();

  function bandLabel(band: string): string {
    return band === "very-low" ? "Very thin market" : "Thin market";
  }
</script>

<section class="ruled-out-panel" id="examined-ruled-out" aria-labelledby="ruled-out-title">
  <header class="ruled-out-head">
    <div class="ruled-out-head-copy">
      <span class="ruled-out-kicker">Screened out</span>
      <h3 id="ruled-out-title">Ideas that did not clear the market-fit check</h3>
      <p>
        These concepts were examined, then excluded from the shortlist. Open an idea to review
        the evidence and assumptions behind that decision.
      </p>
    </div>
    <span class="ruled-out-count">
      {findings.length} {findings.length === 1 ? "idea" : "ideas"}
    </span>
  </header>

  <ol class="ruled-out-list">
    {#each findings as finding, index}
      <li
        class="ruled-out-row"
        class:ruled-out-row--highlight={highlightedIndex === index}
        data-ruled-out-index={index}
      >
        <span class="ruled-out-index">{String(index + 1).padStart(2, "0")}</span>
        <div class="ruled-out-copy">
          <div class="ruled-out-title-line">
            <h4>{finding.idea_name || finding.pain_title}</h4>
            <!-- Marks the rows a user PAID to have evaluated, so they are findable in
                 the same list as pipeline-screened ideas rather than needing a separate
                 block above the candidates. -->
            {#if finding.source_frame === "user_seed"}
              <span class="ruled-out-badge">Your idea</span>
            {:else if finding.source_frame === "owner_synthesis"}
              <span class="ruled-out-badge">Evaluated on request</span>
            {/if}
            <span class="ruled-out-band">{bandLabel(finding.market_fit_band)}</span>
          </div>
          <p class="ruled-out-reason">
            <strong>Why it was ruled out</strong>
            <span>{finding.reason}</span>
          </p>
          {#if finding.idea_name && finding.idea_name !== finding.pain_title}
            <p class="ruled-out-provenance">
              <strong>Pain evaluated</strong>
              <span>{finding.pain_title}</span>
            </p>
          {/if}
        </div>
        <button
          type="button"
          class="ruled-out-view"
          aria-label={`View analysis for ${finding.idea_name || finding.pain_title}`}
          onclick={() => onOpen(finding)}
        >
          View analysis
          <ArrowRight aria-hidden="true" />
        </button>
      </li>
    {/each}
  </ol>
</section>

<style>
  .ruled-out-panel {
    display: grid;
    gap: var(--space-4);
    padding-top: var(--space-5);
    border-top: 1px solid var(--color-border);
  }
  .ruled-out-head {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: var(--space-4);
    align-items: start;
  }
  .ruled-out-head-copy {
    display: grid;
    gap: var(--space-1);
  }
  .ruled-out-kicker {
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: var(--tracking-wide);
    text-transform: uppercase;
  }
  .ruled-out-head h3,
  .ruled-out-head p,
  .ruled-out-title-line h4,
  .ruled-out-reason,
  .ruled-out-provenance {
    margin: 0;
  }
  .ruled-out-head h3 {
    color: var(--color-text-primary);
    font-family: var(--font-display);
    font-size: var(--text-xl);
    font-weight: 700;
    line-height: var(--leading-tight);
    text-wrap: balance;
  }
  .ruled-out-head p {
    max-width: 68ch;
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    line-height: var(--leading-relaxed);
    text-wrap: pretty;
  }
  .ruled-out-count {
    display: inline-flex;
    align-items: center;
    min-height: var(--space-8);
    padding: 0 var(--space-3);
    border-radius: var(--radius-full);
    background: var(--color-bg-surface);
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 600;
    white-space: nowrap;
  }
  .ruled-out-list {
    display: grid;
    margin: 0;
    padding: 0;
    border-top: 1px solid var(--color-border);
    border-bottom: 1px solid var(--color-border);
    list-style: none;
  }
  .ruled-out-row {
    display: grid;
    grid-template-columns: var(--space-8) minmax(0, 1fr) auto;
    gap: var(--space-4);
    align-items: start;
    padding: var(--space-4) 0;
    border-top: 1px solid var(--color-border);
    background: transparent;
  }
  .ruled-out-row:first-child {
    border-top: 0;
  }
  .ruled-out-index {
    padding-top: var(--space-1);
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }
  .ruled-out-copy {
    display: grid;
    gap: var(--space-2);
    min-width: 0;
  }
  .ruled-out-title-line {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--space-2);
  }
  .ruled-out-title-line h4 {
    color: var(--color-text-primary);
    font-family: var(--font-body);
    font-size: var(--text-base);
    font-weight: 700;
    line-height: var(--leading-snug);
    overflow-wrap: anywhere;
  }
  .ruled-out-badge,
  .ruled-out-band {
    display: inline-flex;
    align-items: center;
    min-height: var(--space-5);
    padding: 0 var(--space-2);
    border-radius: var(--radius-full);
    font-size: var(--text-xs);
    font-weight: 700;
    line-height: 1;
    white-space: nowrap;
  }
  .ruled-out-badge {
    border: 1px solid var(--color-border);
    background: var(--color-bg-surface);
    color: var(--color-text-secondary);
  }
  .ruled-out-band {
    border: 1px solid color-mix(in srgb, var(--color-warning) 32%, var(--color-border));
    background: var(--color-warning-subtle);
    color: var(--color-warning-text);
  }
  .ruled-out-reason,
  .ruled-out-provenance {
    display: grid;
    grid-template-columns: max-content minmax(0, 1fr);
    gap: var(--space-2);
    max-width: 82ch;
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    line-height: var(--leading-normal);
    text-wrap: pretty;
  }
  .ruled-out-reason strong,
  .ruled-out-provenance strong {
    color: var(--color-text-secondary);
    font-weight: 600;
  }
  .ruled-out-provenance {
    color: var(--color-text-muted);
  }
  .ruled-out-view {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    min-height: var(--space-8);
    padding: 0 var(--space-2);
    border: 0;
    border-radius: var(--radius-md);
    background: transparent;
    color: var(--color-accent-dark);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: var(--tracking-wide);
    text-transform: uppercase;
    white-space: nowrap;
    cursor: pointer;
    transition:
      background var(--duration-fast) var(--ease-default),
      color var(--duration-fast) var(--ease-default),
      transform var(--duration-fast) var(--ease-default);
  }
  .ruled-out-view:hover {
    background: var(--color-accent-subtle);
  }
  .ruled-out-view:active {
    transform: scale(0.97);
  }
  .ruled-out-view:disabled {
    cursor: not-allowed;
    opacity: 0.5;
  }
  .ruled-out-view :global(svg) {
    width: var(--space-3);
    height: var(--space-3);
  }
  .ruled-out-row--highlight {
    animation: ruled-out-flash var(--duration-slow) var(--ease-default) 4;
  }
  @keyframes ruled-out-flash {
    0%,
    30% {
      background: color-mix(in srgb, var(--color-accent) 12%, transparent);
    }
    100% {
      background: transparent;
    }
  }
  @media (max-width: 760px) {
    .ruled-out-head {
      grid-template-columns: 1fr;
    }
    .ruled-out-count {
      justify-self: start;
    }
    .ruled-out-row {
      grid-template-columns: var(--space-6) minmax(0, 1fr);
      gap: var(--space-3);
    }
    .ruled-out-view {
      grid-column: 2;
      justify-self: start;
      padding: 0;
    }
    .ruled-out-reason,
    .ruled-out-provenance {
      grid-template-columns: 1fr;
      gap: var(--space-1);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .ruled-out-row--highlight {
      animation: none;
      outline: 2px solid var(--color-accent);
      outline-offset: -2px;
    }
    .ruled-out-view {
      transition: none;
    }
    .ruled-out-view:active {
      transform: none;
    }
  }
</style>
