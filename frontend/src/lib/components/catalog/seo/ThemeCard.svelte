<script lang="ts">
  import type { Theme } from "$lib/types/publicCatalog.js";
  import type { PainPointPreview } from "$lib/types/catalog-landing.js";
  import PainPointMiniRow from "./PainPointMiniRow.svelte";

  // Theme card — single column editorial layout.
  //   - Header: mono kicker meta (THEME NN · FREQUENCY · NN mentions)
  //   - Title + description
  //   - Optional "Top pain points" mini-list (when painPoints prop populated)
  //   - Optional "Primary users" footer (when theme.primaryUserSegments populated)
  //
  // The card carries a stable `id="theme-{theme.id}"` so theme chips in the
  // ranked-pain table can deep-link via #theme-{id} and trigger the inset
  // accent ring on `:target`.

  interface Props {
    theme: Theme;
    /** 0-based index — used for `.catalog-fade-in` stagger and as the
     *  default kicker number (`String(index + 1).padStart(2, "0")`).
     *  See `displayNumber` for cases where the visible number diverges
     *  from the render index (sub-niche page offsets to start at 02). */
    index: number;
    /** 1-based number rendered in the kicker. Defaults to `index + 1`.
     *  Sub-niche page passes `index + 2` so other-themes start at 02
     *  after the dominant theme (matches ideas-v2 mock). */
    displayNumber?: number;
    /** Pre-sliced pain points for this theme. Caller controls slicing —
     *  ThemeCard renders all rows it receives. When empty/undefined, the
     *  mini-list section is suppressed entirely. */
    painPoints?: PainPointPreview[];
    /** When provided, renders a "View all pain points →" footer link
     *  below the mini-list anchoring to this href. Caller sets only when
     *  the passed slice is incomplete. */
    viewAllHref?: string;
  }

  let {
    theme,
    index,
    displayNumber,
    painPoints = [],
    viewAllHref,
  }: Props = $props();

  const formattedNumber = $derived(
    String(displayNumber ?? index + 1).padStart(2, "0"),
  );
  const frequencyLabel = $derived(
    theme.frequency ? theme.frequency.toUpperCase() : null,
  );
  const segmentChips = $derived(
    theme.primaryUserSegments && theme.primaryUserSegments.length > 0
      ? theme.primaryUserSegments
      : theme.sources && theme.sources.length > 0
        ? theme.sources
        : null,
  );
  const anchorId = $derived(
    theme.id ? `theme-${theme.id}` : `theme-orphan-${index}`,
  );
  const animationDelay = $derived(`${Math.min(index, 5) * 0.06}s`);
</script>

<article
  id={anchorId}
  class="theme-card catalog-fade-in"
  style:animation-delay={animationDelay}
>
  <div class="tc-meta">
    <span class="tc-num">THEME {formattedNumber}</span>
    {#if frequencyLabel}
      <span class="tc-dot" aria-hidden="true">·</span>
      <span class="tc-freq" data-frequency={frequencyLabel.toLowerCase()}>{frequencyLabel}</span>
    {/if}
    {#if theme.mentionCount != null}
      <span class="tc-dot" aria-hidden="true">·</span>
      <span class="tc-mentions">{theme.mentionCount.toLocaleString()} mentions</span>
    {/if}
  </div>

  <h3 class="tc-title">{theme.title}</h3>

  {#if theme.description}
    <p class="tc-desc">{theme.description}</p>
  {/if}

  {#if painPoints.length > 0}
    <div class="tc-pains">
      <span class="tc-pains-kicker">Top pain points</span>
      <ul class="tc-pains-list">
        {#each painPoints as pp (pp.id)}
          <li><PainPointMiniRow painPoint={pp} /></li>
        {/each}
      </ul>
      {#if viewAllHref}
        <a class="tc-pains-foot" href={viewAllHref}>
          View all pain points <span aria-hidden="true">→</span>
        </a>
      {/if}
    </div>
  {/if}

  {#if segmentChips}
    <div class="tc-segs">
      <span class="tc-segs-kicker">Primary users</span>
      <ul class="tc-segs-list">
        {#each segmentChips as seg}
          <li>{seg}</li>
        {/each}
      </ul>
    </div>
  {/if}
</article>

<style>
  .theme-card {
    position: relative;
    background: var(--color-bg-elevated, #fff);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    padding: 22px 24px;
  }

  /* Header meta row — mono kicker style matching the catalog system. */
  .tc-meta {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 600;
    color: var(--color-text-muted);
  }
  .tc-num {
    color: var(--color-accent);
    font-weight: 700;
  }
  .tc-dot {
    margin: 0 8px;
    opacity: 0.55;
  }
  .tc-freq {
    color: var(--color-text-muted);
  }
  .tc-freq[data-frequency="high"] {
    color: var(--color-accent);
  }
  .tc-freq[data-frequency="medium"] {
    color: var(--color-text-primary);
  }
  .tc-freq[data-frequency="low"] {
    opacity: 0.7;
  }
  .tc-mentions {
    color: var(--color-text-muted);
  }

  .tc-title {
    font-size: 16px;
    font-weight: 600;
    letter-spacing: -0.01em;
    line-height: 1.3;
    color: var(--color-text-primary);
    text-wrap: balance;
    max-width: 720px;
    margin: 10px 0 8px;
  }
  .tc-desc {
    font-size: 13.5px;
    color: var(--color-text-secondary, var(--color-text-primary));
    line-height: 1.6;
    max-width: 680px;
    margin: 0;
    overflow-wrap: anywhere;
  }

  /* Top-pain-points mini-list — quieter sub-section with dashed top divider. */
  .tc-pains {
    margin-top: 20px;
    padding-top: 14px;
    border-top: 1px dashed var(--color-border);
  }
  .tc-pains-kicker {
    display: block;
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 700;
    color: var(--color-text-muted);
    margin-bottom: 8px;
  }
  .tc-pains-list {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .tc-pains-list li {
    border-bottom: 1px dashed var(--color-border);
  }
  .tc-pains-list li:last-child {
    border-bottom: none;
  }
  .tc-pains-foot {
    display: block;
    text-align: right;
    margin-top: 8px;
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--color-text-muted);
    text-decoration: none;
    transition: color 0.12s;
  }
  .tc-pains-foot:hover {
    color: var(--color-text-primary);
  }

  /* Primary-users footer — quiet inline list under a mono kicker; matches
     the editorial pattern used by DominantTheme. */
  .tc-segs {
    margin-top: 18px;
    padding-top: 14px;
    border-top: 1px solid var(--color-border);
  }
  .tc-segs-kicker {
    display: block;
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 700;
    color: var(--color-text-muted);
    margin-bottom: 6px;
  }
  .tc-segs-list {
    list-style: none;
    margin: 0;
    padding: 0;
    font-size: 12.5px;
    line-height: 1.55;
    color: var(--color-text-secondary, var(--color-text-primary));
    overflow-wrap: anywhere;
  }
  .tc-segs-list li {
    display: inline;
  }
  .tc-segs-list li:not(:first-child)::before {
    content: " · ";
    color: var(--color-text-muted);
    opacity: 0.6;
  }

  /* :target highlight — chip in the ranked-pain table anchors here.
     Inset pseudo-element survives any overflow:hidden on ancestors. */
  .theme-card:target::after {
    content: "";
    position: absolute;
    inset: 0;
    border: 2px solid var(--color-accent);
    border-radius: inherit;
    pointer-events: none;
    animation: tc-flash 1.2s var(--ease-out) forwards;
  }
  @keyframes tc-flash {
    0%,
    40% {
      opacity: 1;
    }
    100% {
      opacity: 0;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .theme-card:target::after {
      animation: none;
      opacity: 1;
    }
  }

  @media (max-width: 640px) {
    .theme-card {
      padding: 18px 18px;
    }
    .tc-title {
      font-size: 15px;
    }
  }
</style>
