<script lang="ts">
  import type { Theme } from "$lib/types/publicCatalog.js";
  import type { PainPointPreview } from "$lib/types/catalog-landing.js";
  import PainPointMiniRow from "./PainPointMiniRow.svelte";

  // Featured callout for the highest-mention theme on a sub-niche page.
  // Dominant signal block: ranked kicker, mention stat, and primary user
  // segments rendered as a quiet inline list under a mono kicker.
  // Sits above the broader theme list.

  interface Props {
    theme: Theme | null;
    /** "Most-cited theme" / similar override. */
    label?: string;
    /** Top pain points associated with this theme (already filtered + sorted
     *  by severity desc upstream). When supplied with ≥1 entry, render a
     *  quiet preview list above the footer stat row. Capped at the caller's
     *  desired length — no further trimming here. */
    topPainPoints?: PainPointPreview[];
  }

  let { theme, label = "Most-cited theme", topPainPoints = [] }: Props = $props();

  // Anchor id is only emitted when theme.id is non-null; legacy themes
  // without a stable id stay un-anchored (no broken `id="theme-null"`).
  const anchorId = $derived(theme?.id ? `theme-${theme.id}` : undefined);
</script>

{#if theme}
  <article class="dt" id={anchorId}>
    <div class="dt-marker">
      <span class="dt-num">01</span>
      <span class="dt-label">{label}</span>
    </div>
    <h2>{theme.title}</h2>
    {#if theme.description}
      <p class="dt-desc">{theme.description}</p>
    {/if}
    {#if topPainPoints.length > 0}
      <div class="mini-block">
        <span class="mini-kicker">Top pain points</span>
        <ul class="mini-rows">
          {#each topPainPoints as pp (pp.id)}
            <li><PainPointMiniRow painPoint={pp} /></li>
          {/each}
        </ul>
      </div>
    {/if}
    <div class="dt-foot">
      {#if theme.mentionCount != null}
        <div class="dt-stat">
          <span class="n">{theme.mentionCount.toLocaleString()}</span>
          <span class="l">Mentions across forums</span>
        </div>
      {/if}
      {#if theme.primaryUserSegments && theme.primaryUserSegments.length > 0}
        <div class="dt-segments">
          <span class="dt-seg-key">Primary users</span>
          <ul class="dt-seg-list">
            {#each theme.primaryUserSegments as seg}
              <li>{seg}</li>
            {/each}
          </ul>
        </div>
      {/if}
    </div>
  </article>
{/if}

<style>
  .dt {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    padding: 24px 28px;
    margin: 8px 0 24px;
    position: relative;
  }
  .dt-marker {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 14px;
  }
  .dt-num {
    font-family: var(--font-mono);
    font-size: 13px;
    font-weight: 700;
    color: var(--color-accent);
    letter-spacing: 0.04em;
    background: var(--color-accent-subtle, rgba(234, 88, 12, 0.08));
    padding: 3px 8px;
    border-radius: 4px;
  }
  .dt-label {
    font-size: 10px;
    color: var(--color-text-muted);
    letter-spacing: 0.1em;
    text-transform: uppercase;
    font-weight: 700;
    font-family: var(--font-mono);
  }
  h2 {
    font-size: 24px;
    font-weight: 600;
    letter-spacing: -0.02em;
    line-height: 1.25;
    color: var(--color-text-primary);
    text-wrap: balance;
    max-width: 720px;
    margin: 0 0 10px;
  }
  .dt-desc {
    font-size: 14.5px;
    color: var(--color-text-secondary, var(--color-text-primary));
    line-height: 1.65;
    max-width: 760px;
    margin: 0;
  }
  .dt-foot {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 24px;
    margin-top: 18px;
    padding-top: 18px;
    border-top: 1px solid var(--color-border);
    flex-wrap: wrap;
  }
  .dt-stat {
    display: flex;
    align-items: baseline;
    gap: 8px;
  }
  .dt-stat .n {
    font-family: var(--font-mono);
    font-size: 24px;
    font-weight: 600;
    color: var(--color-text-primary);
    letter-spacing: -0.02em;
    line-height: 1;
  }
  .dt-stat .l {
    font-size: 12px;
    color: var(--color-text-muted);
  }
  /* Primary-user segments — quiet inline list under a mono kicker.
     Replaces the previous flex-wrap `<Chip>` row so the footer matches the
     editorial voice established in the niche-context block above the hero. */
  .dt-segments {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
    min-width: 0;
    max-width: 56ch;
  }
  .dt-seg-key {
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 700;
    color: var(--color-text-muted);
  }
  .dt-seg-list {
    list-style: none;
    margin: 0;
    padding: 0;
    font-size: 12.5px;
    line-height: 1.55;
    color: var(--color-text-secondary, var(--color-text-primary));
    overflow-wrap: anywhere;
  }
  .dt-seg-list li {
    display: inline;
  }
  .dt-seg-list li:not(:first-child)::before {
    content: " · ";
    color: var(--color-text-muted);
    opacity: 0.6;
    /* Decorative — SR uses the <li> structure, not this glyph. */
  }

  /* Mobile: footer wraps under mention stat */
  @media (max-width: 700px) {
    .dt-foot {
      flex-direction: column;
      align-items: flex-start;
      gap: 12px;
    }
  }

  /* Mini-list — preview of this theme's top pain points. Shares visual
     language with the mini-list in PainPointsByTheme but sits inside the
     dominant-callout surface, so spacing is slightly looser. */
  .mini-block {
    margin-top: 18px;
    padding-top: 16px;
    border-top: 1px solid var(--color-border);
  }
  .mini-kicker {
    display: block;
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 700;
    color: var(--color-text-muted);
    margin-bottom: 6px;
  }
  .mini-rows {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .mini-rows li {
    border-bottom: 1px dashed var(--color-border);
  }
  .mini-rows li:last-child {
    border-bottom: none;
  }
  /* Inner mini-row markup is now provided by <PainPointMiniRow>. The
     `.mini-row*`/`.mini-title*`/`.mini-meta*` rules previously here have
     moved to that shared component. */

  /* :target — chip in the ranked-pain table anchors to this card.
     A quiet bg pulse signals the jump without stacking an accent border. */
  .dt:target {
    animation: dt-flash 1.2s var(--ease-out) forwards;
  }
  @keyframes dt-flash {
    0%,
    40% {
      background-color: rgba(234, 88, 12, 0.08);
    }
    100% {
      background-color: var(--color-surface);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .dt:target {
      animation: none;
      outline: 2px solid var(--color-accent);
      outline-offset: -2px;
    }
  }
</style>
