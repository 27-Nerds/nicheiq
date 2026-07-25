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
      <AnnotationSurface surfaceKey={`ruled-out-detail:${title}`}>
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
        <section class="verdict">
          <h3>Why it was ruled out</h3>
          <p>{finding.reason}</p>
        </section>
        <dl class="facts">
          <div><dt>Pain evaluated</dt><dd>{finding.pain_title}</dd></div>
          <div>
            <dt>Market fit</dt>
            <dd>{marketFit !== null ? `${Math.round(marketFit * 100)}%` : "Not scored"}</dd>
          </div>
          {#if idea?.estimated_development_time}
            <div><dt>Build estimate</dt><dd>{idea.estimated_development_time}</dd></div>
          {/if}
        </dl>
        {#if finding.evidence?.trim()}
          <section>
            <h3>Evidence considered</h3>
            <blockquote>&ldquo;{finding.evidence}&rdquo;</blockquote>
          </section>
        {/if}
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
    border: 1px solid var(--color-border);
    border-radius: 0.75rem;
    background: var(--color-bg-surface);
  }
  .detail-head {
    position: relative;
    display: grid;
    gap: 0.55rem;
    padding: 1.35rem 4rem 1.15rem 1.5rem;
    border-bottom: 1px solid var(--color-border);
  }
  .detail-head h2 {
    margin: 0;
    color: var(--color-text-primary);
    font-size: 1.35rem;
    line-height: 1.15;
  }
  .detail-kicker,
  .detail-body h3,
  .facts dt {
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 800;
    letter-spacing: 0.07em;
    text-transform: uppercase;
  }
  .detail-badges { display: flex; gap: 0.4rem; }
  .detail-close {
    position: absolute;
    top: 1rem;
    right: 1rem;
    display: grid;
    width: 2rem;
    height: 2rem;
    padding: 0;
    place-items: center;
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
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
  .detail-close :global(svg) { width: 1rem; height: 1rem; }
  .detail-body {
    display: grid;
    gap: 1rem;
    padding: 1.25rem 1.5rem 1.5rem;
    overflow-y: auto;
  }
  .detail-body section { display: grid; gap: 0.35rem; }
  .detail-body h3,
  .detail-body p,
  .detail-body blockquote { margin: 0; }
  .detail-body p,
  .detail-body li,
  .detail-body dd {
    color: var(--color-text-secondary);
    font-size: 0.875rem;
    line-height: 1.55;
    overflow-wrap: anywhere;
  }
  .verdict {
    padding: 0.85rem 0.95rem;
    border: 1px solid var(--color-border);
    background: var(--color-bg-surface);
  }
  .facts {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
    gap: 0.75rem;
    margin: 0;
  }
  .facts div {
    display: grid;
    gap: 0.25rem;
    padding: 0.75rem;
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
  }
  .facts dd { margin: 0; }
  .detail-body blockquote {
    padding-left: 0.75rem;
    border-left: 1px solid var(--color-border-emphasis);
    color: var(--color-text-secondary);
    font-size: 0.875rem;
    font-style: italic;
    line-height: 1.5;
  }
  .badge,
  .band {
    display: inline-flex;
    align-items: center;
    padding: 0.06rem 0.36rem;
    border-radius: 0.375rem;
    white-space: nowrap;
  }
  .badge {
    border: 1px solid color-mix(in srgb, var(--color-accent) 40%, transparent);
    background: color-mix(in srgb, var(--color-accent) 10%, transparent);
    color: var(--color-accent-dark);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 800;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }
  .band {
    border: 1px solid var(--color-border);
    background: var(--color-bg-surface);
    color: var(--color-text-secondary);
    font-family: var(--font-body);
    font-size: 0.625rem;
    font-weight: 700;
  }
  @media (prefers-reduced-motion: reduce) {
    .detail-close:active { transform: none; }
  }
</style>
