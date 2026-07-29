<script lang="ts">
  import { X } from "lucide-svelte";
  import AnnotationSurface from "$lib/components/annotations/AnnotationSurface.svelte";
  import WorkspaceOverlay from "$lib/components/ui/WorkspaceOverlay.svelte";
  import type { RuledOutFinding } from "$lib/types/report";
  import { finiteUnitScore } from "$lib/utils/displayGuards";

  interface Props {
    finding: RuledOutFinding;
    onClose: () => void;
  }

  let { finding, onClose }: Props = $props();

  const idea = $derived(finding.idea);
  const title = $derived(finding.idea_name || finding.pain_title);
  const marketFit = $derived(finiteUnitScore(finding.market_fit));
  const bandLabel = $derived(finding.market_fit_band === "very-low" ? "Very thin market" : "Thin market");
</script>

<WorkspaceOverlay open={true} size="standard" label={`Ruled-out analysis: ${title}`} {onClose}>
  <article class="detail-card">
    <header class="detail-head">
      <span class="detail-kicker">Examined &amp; ruled out</span>
      <h2>{title}</h2>
      <div class="detail-badges">
        {#if finding.source_frame === "user_seed"}<span class="badge">Your idea</span>{/if}
        <span class="band">{bandLabel}</span>
      </div>
      <button type="button" class="detail-close" aria-label="Close ruled-out analysis" onclick={onClose}>
        <X aria-hidden="true" />
      </button>
    </header>
    <div class="detail-body">
      <AnnotationSurface class="detail-content" surfaceKey={`ruled-out-detail:${title}`}>
        <div class="rationale">
          <section class="verdict">
            <h3>Why it was ruled out</h3>
            <p>{finding.reason}</p>
          </section>

          {#if finding.evidence?.trim()}
            <section class="evidence">
              <h3>Evidence considered</h3>
              <blockquote>&ldquo;{finding.evidence}&rdquo;</blockquote>
            </section>
          {/if}
        </div>

        {#if idea?.short_description || idea?.description || idea?.value_proposition}
          <div class="overview-grid">
            {#if idea?.short_description || idea?.description}
              <section>
                <h3>What it does</h3>
                <p>{idea.short_description || idea.description}</p>
              </section>
            {/if}
            {#if idea?.value_proposition}
              <section>
                <h3>Value proposition</h3>
                <p>{idea.value_proposition}</p>
              </section>
            {/if}
          </div>
        {/if}

        <dl class="facts" class:facts--two={!idea?.estimated_development_time}>
          <div><dt>Pain evaluated</dt><dd>{finding.pain_title}</dd></div>
          <div>
            <dt>Market fit</dt>
            <dd>{marketFit !== null ? `${Math.round(marketFit * 100)}%` : "Not scored"}</dd>
          </div>
          {#if idea?.estimated_development_time}
            <div><dt>Build estimate</dt><dd>{idea.estimated_development_time}</dd></div>
          {/if}
        </dl>
        {#if idea?.core_features?.length}
          <section>
            <h3>Core features</h3>
            <ul>{#each idea.core_features as feature}<li>{feature}</li>{/each}</ul>
          </section>
        {/if}
      </AnnotationSurface>
    </div>
  </article>
</WorkspaceOverlay>

<style>
  .detail-card {
    display: flex;
    flex-direction: column;
    max-height: 100%;
    overflow: hidden;
    background: var(--color-bg-elevated);
  }
  .detail-head {
    position: relative;
    display: grid;
    gap: var(--space-2);
    padding: var(--space-6) var(--space-16) var(--space-5) var(--space-6);
    border-bottom: 1px solid var(--color-border);
  }
  .detail-head h2 {
    margin: 0;
    color: var(--color-text-primary);
    font-family: var(--font-display);
    font-size: var(--text-3xl);
    font-weight: 700;
    line-height: 1.2;
    letter-spacing: -0.025em;
    text-wrap: balance;
  }
  .detail-kicker,
  .facts dt {
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.07em;
    text-transform: uppercase;
  }
  .detail-body h3 {
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.07em;
    text-transform: uppercase;
  }
  .detail-badges {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }
  .detail-close {
    position: absolute;
    top: var(--space-5);
    right: var(--space-5);
    display: grid;
    width: var(--space-10);
    height: var(--space-10);
    padding: 0;
    place-items: center;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-bg-elevated);
    color: var(--color-text-secondary);
    cursor: pointer;
    transition:
      background var(--duration-fast) var(--ease-default),
      border-color var(--duration-fast) var(--ease-default),
      color var(--duration-fast) var(--ease-default);
  }
  .detail-close:hover {
    border-color: var(--color-border-emphasis);
    background: var(--color-bg-surface);
    color: var(--color-text-primary);
  }
  .detail-close:active { transform: scale(0.96); }
  .detail-close:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .detail-close :global(svg) {
    width: var(--space-5);
    height: var(--space-5);
  }
  .detail-body {
    padding: var(--space-6);
    overflow-y: auto;
  }
  .detail-body :global(.detail-content) {
    display: grid;
    gap: var(--space-6);
  }
  .detail-body section {
    display: grid;
    gap: var(--space-2);
    align-content: start;
  }
  .detail-body h3,
  .detail-body p,
  .detail-body blockquote { margin: 0; }
  .detail-body p,
  .detail-body li,
  .detail-body dd {
    color: var(--color-text-secondary);
    font-size: var(--text-base);
    line-height: 1.55;
    overflow-wrap: anywhere;
  }
  .rationale {
    overflow: hidden;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-bg-elevated);
  }
  .verdict {
    padding: var(--space-5) var(--space-6);
    background: var(--color-warning-subtle);
  }
  .verdict h3 {
    color: var(--color-warning-text);
  }
  .verdict p {
    max-width: 68ch;
    color: var(--color-text-primary);
    font-size: var(--text-md);
    font-weight: 500;
    line-height: 1.55;
    text-wrap: pretty;
  }
  .overview-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-6);
  }
  .overview-grid section:only-child {
    grid-column: 1 / -1;
  }
  .facts {
    display: grid;
    grid-template-columns: minmax(0, 1.5fr) repeat(2, minmax(0, 1fr));
    margin: 0;
    overflow: hidden;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-bg-surface);
  }
  .facts.facts--two {
    grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr);
  }
  .facts div {
    display: grid;
    gap: var(--space-2);
    align-content: start;
    padding: var(--space-4);
  }
  .facts div + div {
    border-left: 1px solid var(--color-border);
  }
  .facts dd {
    margin: 0;
    color: var(--color-text-primary);
    font-size: var(--text-base);
    font-weight: 600;
    line-height: 1.45;
  }
  .evidence {
    padding: var(--space-4) var(--space-6) var(--space-5);
    border-top: 1px solid var(--color-border);
  }
  .evidence blockquote {
    max-width: 68ch;
    color: var(--color-text-secondary);
    font-size: var(--text-base);
    font-style: normal;
    line-height: 1.55;
    text-wrap: pretty;
  }
  .detail-body ul {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-2) var(--space-6);
    margin: 0;
    padding-left: var(--space-5);
  }
  .detail-body li::marker {
    color: var(--color-text-muted);
  }
  .badge,
  .band {
    display: inline-flex;
    align-items: center;
    min-height: var(--space-6);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-md);
    white-space: nowrap;
  }
  .badge {
    border: 1px solid var(--color-border);
    background: var(--color-bg-surface);
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 800;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }
  .band {
    border: 1px solid var(--color-border-warning);
    background: var(--color-warning-subtle);
    color: var(--color-warning-text);
    font-family: var(--font-body);
    font-size: var(--text-sm);
    font-weight: 700;
  }
  @media (max-width: 639px) {
    .detail-head {
      padding: var(--space-5) var(--space-16) var(--space-4) var(--space-5);
    }
    .detail-head h2 {
      font-size: var(--text-2xl);
    }
    .detail-close {
      top: var(--space-4);
      right: var(--space-4);
    }
    .detail-body {
      padding: var(--space-5);
    }
    .detail-body :global(.detail-content) {
      gap: var(--space-5);
    }
    .overview-grid,
    .detail-body ul {
      grid-template-columns: 1fr;
    }
    .facts {
      grid-template-columns: 1fr;
    }
    .facts div + div {
      border-top: 1px solid var(--color-border);
      border-left: 0;
    }
    .verdict,
    .evidence {
      padding: var(--space-4);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .detail-close:active { transform: none; }
  }
</style>
