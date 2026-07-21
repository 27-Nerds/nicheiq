<script lang="ts">
  import type { AudienceSignals } from "$lib/types/publicCatalog.js";
  import Chip from "./Chip.svelte";

  // Hairline-divided rows rendering all 8 fields of the AudienceSignals
  // payload. 2-col grid on ≥768px so chip rows pair side-by-side; bullet/prose
  // rows span both columns. Rows render only when their data is present;
  // the section hides entirely if every field is empty.

  interface Props {
    signals: AudienceSignals;
    /** Compact mode: lighter chrome, muted (non-accent) labels, tighter
     *  padding. Used on consumer pages where the section sits next to other
     *  bordered content (e.g. /idea/[slug]) and the dense bordered grid would
     *  read as a control panel. Sub-niche page leaves this false (the section
     *  IS the page meat there). */
    compact?: boolean;
  }

  let { signals, compact = false }: Props = $props();

  const hasTools = $derived(signals.currentTools.length > 0);
  const hasFrustrations = $derived(signals.frustrations.length > 0);
  const hasVocabulary = $derived(signals.vocabulary.length > 0);
  const hasCommunityHubs = $derived(signals.communityHubs.length > 0);
  const hasRecommendedChannels = $derived(signals.recommendedChannels.length > 0);
  const hasMessagingFrameworks = $derived(signals.messagingFrameworks.length > 0);
  const hasContentPreferences = $derived(
    !!signals.contentPreferences && signals.contentPreferences.trim().length > 0,
  );
  const hasEarlyAdopterTactics = $derived(
    !!signals.earlyAdopterTactics && signals.earlyAdopterTactics.trim().length > 0,
  );
  const hasAny = $derived(
    hasTools ||
      hasFrustrations ||
      hasVocabulary ||
      hasCommunityHubs ||
      hasRecommendedChannels ||
      hasMessagingFrameworks ||
      hasContentPreferences ||
      hasEarlyAdopterTactics,
  );
</script>

{#if hasAny}
  {#if compact}
    <p class="signals-deck-text">
      What they use, where they gather, and how to talk to them, observed in source discussions.
    </p>
  {/if}
  <div class="signals-list" class:compact>
    {#if hasTools}
      <div class="row half">
        <span class="row-label">
          Tools they use today
          <span class="row-sep" aria-hidden="true">·</span>
          <span class="row-count">{signals.currentTools.length}</span>
        </span>
        <div class="chips">
          {#each signals.currentTools as t}
            <Chip label={t} />
          {/each}
        </div>
      </div>
    {/if}
    {#if hasCommunityHubs}
      <div class="row half">
        <span class="row-label">
          Where they gather
          <span class="row-sep" aria-hidden="true">·</span>
          <span class="row-count">{signals.communityHubs.length}</span>
        </span>
        <div class="chips">
          {#each signals.communityHubs as c}
            <Chip label={c} />
          {/each}
        </div>
      </div>
    {/if}
    {#if hasVocabulary}
      <div class="row half">
        <span class="row-label">
          How they describe it
          <span class="row-sep" aria-hidden="true">·</span>
          <span class="row-count">{signals.vocabulary.length}</span>
        </span>
        <div class="chips vocab">
          {#each signals.vocabulary as v}
            <Chip label={v} mono />
          {/each}
        </div>
      </div>
    {/if}
    {#if hasRecommendedChannels}
      <div class="row half">
        <span class="row-label">
          Where to reach them
          <span class="row-sep" aria-hidden="true">·</span>
          <span class="row-count">{signals.recommendedChannels.length}</span>
        </span>
        <div class="chips">
          {#each signals.recommendedChannels as c}
            <Chip label={c} />
          {/each}
        </div>
      </div>
    {/if}
    {#if hasFrustrations}
      <div class="row full">
        <span class="row-label">
          Frustrations with current tools
          <span class="row-sep" aria-hidden="true">·</span>
          <span class="row-count">{signals.frustrations.length}</span>
        </span>
        <ul class="bullets">
          {#each signals.frustrations as f}
            <li>{f}</li>
          {/each}
        </ul>
      </div>
    {/if}
    {#if hasMessagingFrameworks}
      <div class="row full">
        <span class="row-label">
          Messaging that resonates
          <span class="row-sep" aria-hidden="true">·</span>
          <span class="row-count">{signals.messagingFrameworks.length}</span>
        </span>
        <ul class="bullets">
          {#each signals.messagingFrameworks as m}
            <li>{m}</li>
          {/each}
        </ul>
      </div>
    {/if}
    {#if hasContentPreferences}
      <div class="row full">
        <span class="row-label">Content they value</span>
        <p class="prose">{signals.contentPreferences}</p>
      </div>
    {/if}
    {#if hasEarlyAdopterTactics}
      <div class="row full">
        <span class="row-label">Early-adopter tactics</span>
        <p class="prose">{signals.earlyAdopterTactics}</p>
      </div>
    {/if}
  </div>
{/if}

<style>
  /* DEFAULT — sub-niche page idiom. 2-col grid with 1px-gap-on-border-bg
     trick so each row reads as a tile in a control panel. Accent-colored
     mono labels work because the section IS the focal block on that page. */
  .signals-list {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1px;
    background: var(--color-border);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    overflow: hidden;
  }
  @media (max-width: 768px) {
    .signals-list {
      grid-template-columns: 1fr;
    }
  }
  .row {
    background: var(--color-surface);
    padding: 16px 20px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .row.full {
    grid-column: 1 / -1;
  }
  .row-label {
    display: block;
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--color-accent-muted);
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .row-sep {
    opacity: 0.55;
    margin: 0 4px;
  }
  .row-count {
    color: var(--color-text-secondary);
    font-feature-settings: "tnum" 1;
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
  }
  .bullets {
    list-style: disc;
    list-style-position: outside;
    margin: 0;
    padding-left: 18px;
    display: grid;
    gap: 4px;
  }
  .bullets li {
    font-size: 13px;
    color: var(--color-text-secondary, var(--color-text-primary));
    line-height: 1.5;
  }
  .bullets li::marker {
    color: var(--color-text-muted);
  }
  .prose {
    font-size: 13px;
    color: var(--color-text-secondary, var(--color-text-primary));
    line-height: 1.6;
    margin: 0;
    max-width: 780px;
  }

  /* COMPACT — consumer-page idiom (e.g. /idea/[slug]). Flat row grid with
     internal hairline dividers; no outer card chrome. The lede prose sits
     OUTSIDE this container (rendered above it in the JSX) so audience
     signals matches the Themes / Search-opportunity flat-lede pattern.

     Layout: CSS grid 2-col on desktop. Chip rows take their natural slot;
     prose rows span both columns (grid-column: 1 / -1). */
  /* Outer horizontal padding insets the dashed row-borders from the section
     edges (matching the DataList pattern where rows sit inside a padded
     parent). Row padding loses its horizontal component since the parent
     now provides the inset; column-divider breathing room is added back
     selectively on paired half-rows below. */
  .signals-list.compact {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0;
    padding: 0 24px;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    overflow: hidden;
  }
  @media (max-width: 768px) {
    .signals-list.compact {
      grid-template-columns: 1fr;
      padding: 0;
    }
  }
  /* Canonical lede — matches `.theme-deck-note` (PainPointsByTheme) and
     `.catalog-deck-text` (idea-page Competitive + Search Opportunity decks). */
  .signals-deck-text {
    display: block;
    max-width: 720px;
    margin: 0 0 18px;
    font-size: 12px;
    line-height: 1.45;
    color: var(--color-text-muted);
    text-wrap: pretty;
    overflow-wrap: anywhere;
  }
  .signals-list.compact > .row {
    padding: 14px 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
    border-top: 1px dashed var(--color-border);
  }
  .signals-list.compact > .row.full {
    grid-column: 1 / -1;
  }
  /* Mobile: restore row horizontal padding when grid collapses to 1-col
     (parent padding is dropped above, so rows need to provide it). */
  @media (max-width: 768px) {
    .signals-list.compact > .row {
      padding: 14px 18px;
    }
  }
  /* Without the outer card, the top row-pair's border-top would read as a
     stray rule above the content. Strip it: the first .row always; the
     second .row only when it pairs with the first in the same visual
     row-pair (both .half so they sit side-by-side at the grid top). */
  .signals-list.compact > .row:first-of-type {
    border-top: none;
  }
  .signals-list.compact > .row.half:first-of-type + .row.half {
    border-top: none;
  }
  /* Column gutter between paired half rows on desktop. No vertical divider —
     matches the gap-only pattern used by the build-sketch grid (which has
     no internal vertical borders either). */
  @media (min-width: 768px) {
    .signals-list.compact > .row.half:nth-of-type(odd) {
      padding-right: 18px;
    }
    .signals-list.compact > .row.half:nth-of-type(odd) + .row.half {
      padding-left: 18px;
    }
  }
  .signals-list.compact .bullets li,
  .signals-list.compact .prose {
    font-size: 12.5px;
    line-height: 1.55;
  }
</style>
