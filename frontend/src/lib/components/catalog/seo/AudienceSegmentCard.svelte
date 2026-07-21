<script lang="ts">
  import type { AudienceSegment } from "$lib/types/publicCatalog.js";
  import { categoryPath } from "$lib/utils/urls";

  interface Props {
    segment: AudienceSegment;
    showSource?: boolean;
  }

  let { segment, showSource = false }: Props = $props();

  const sourceHref = $derived(
    segment.sourceSubNiche
      ? categoryPath({
          slug: segment.sourceSubNiche.slug,
          parentSlug: segment.sourceSubNiche.parentSlug,
        })
      : "",
  );
</script>

<article class="seg">
  {#if segment.sizeLabel}
    <span class="lbl" data-size={segment.sizeLabel.toLowerCase()}>{segment.sizeLabel}</span>
  {/if}
  <h4>{segment.name}</h4>
  {#if segment.bullets.length > 0}
    <ul>
      {#each segment.bullets as it}
        <li>{it}</li>
      {/each}
    </ul>
  {/if}
  {#if segment.expertiseLevel || segment.budgetSensitivity}
    <div class="seg-meta">
      {#if segment.expertiseLevel}<span class="expertise" data-expertise={segment.expertiseLevel.toLowerCase()}>{segment.expertiseLevel}</span>{/if}
      {#if segment.expertiseLevel && segment.budgetSensitivity}<span class="dot">·</span>{/if}
      {#if segment.budgetSensitivity}<span class="budget" data-budget={segment.budgetSensitivity.toLowerCase()}>{segment.budgetSensitivity} budget</span>{/if}
    </div>
  {/if}
  {#if showSource && segment.sourceSubNiche}
    <a class="seg-source" href={sourceHref}>
      <span class="arrow" aria-hidden="true">↗</span>
      <span>From {segment.sourceSubNiche.name}</span>
    </a>
  {/if}
</article>

<style>
  .seg {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: 6px;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .lbl {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--color-accent-muted);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 600;
  }
  /* Size — Demand axis. Mirrors the orange Demand score-bar at the top of
     the page so the segment card reads as a per-segment echo of the same
     opportunity story. Unknown values fall through to accent-muted. */
  .lbl[data-size="large"]  { color: var(--color-accent); }
  .lbl[data-size="medium"] { color: var(--color-text-secondary); }
  .lbl[data-size="small"]  { color: var(--color-text-muted); }
  h4 {
    font-size: 14px;
    font-weight: 600;
    letter-spacing: -0.005em;
    line-height: 1.3;
    color: var(--color-text-primary);
    margin: 0;
  }
  /* Real list markers (not ::before pseudo-elements) so screen readers
     announce "list of N items" — required for a11y. ::marker colors the dot. */
  ul {
    list-style: disc;
    list-style-position: outside;
    display: grid;
    gap: 4px;
    margin: 2px 0 0;
    padding-left: 14px;
  }
  li {
    font-size: 12.5px;
    color: var(--color-text-secondary, var(--color-text-primary));
    line-height: 1.45;
  }
  li::marker {
    color: var(--color-text-muted);
  }
  /* Footer meta line — expertise level + budget sensitivity. Mono so it reads
     as a quiet badge rather than another bullet. */
  .seg-meta {
    margin-top: auto;
    padding-top: 8px;
    border-top: 1px solid var(--color-border);
    font-family: var(--font-mono);
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-accent-muted);
    display: flex;
    gap: 6px;
    align-items: center;
    flex-wrap: wrap;
  }
  .seg-meta .dot {
    color: var(--color-text-muted);
    opacity: 0.6;
  }
  /* Expertise — Feasibility axis (blue family). Deeper blue = deeper skill
     level. All three steps stay inside the existing info-{light,base,dark}
     trio used by the Feasibility score-bar. */
  .seg-meta .expertise[data-expertise="beginner"]     { color: var(--color-info-light); }
  .seg-meta .expertise[data-expertise="intermediate"] { color: var(--color-info); }
  .seg-meta .expertise[data-expertise="advanced"],
  .seg-meta .expertise[data-expertise="expert"]       { color: var(--color-info-dark); }
  /* Budget — Opportunity axis (success green). Mirrors the green Opportunity
     score-bar; high budget = full success, low budget = quiet neutral. */
  .seg-meta .budget[data-budget="high"]   { color: var(--color-success); }
  .seg-meta .budget[data-budget="medium"] { color: var(--color-text-secondary); }
  .seg-meta .budget[data-budget="low"]    { color: var(--color-text-muted); }
  .seg-source {
    min-height: 32px;
    padding-top: 8px;
    border-top: 1px solid var(--color-border);
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 600;
    color: var(--color-accent-muted);
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
    overflow-wrap: anywhere;
    transition: color 0.12s;
  }
  .seg-source:hover {
    color: var(--color-accent);
  }
  .seg-source:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 3px;
    border-radius: 2px;
  }
  .seg-source .arrow {
    color: var(--color-text-muted);
  }
</style>
